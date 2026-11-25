import json
import re
from hashlib import sha256

from django import forms
from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.assessments.models import AssessmentAttempt, BlueprintItemEvidenceSource
from apps.evidence.models import (
    EvidenceIntegration,
    EvidenceRecord,
    EvidenceSource,
    ExternalEvidenceReceipt,
)

ADAPTER_VERSION = "v1"
MAX_PAYLOAD_BYTES = 4096


def token_digest(token: str) -> str:
    return sha256(token.encode("ascii")).hexdigest()


class ExternalEvidenceForm(forms.Form):
    external_id = forms.CharField(max_length=160)
    attempt_id = forms.IntegerField(min_value=1, max_value=2**63 - 1)
    evidence_type = forms.SlugField(max_length=40)
    reference = forms.CharField(max_length=160)
    context = forms.CharField(max_length=250, required=False)


def error_response(code: str, status: int) -> JsonResponse:
    return JsonResponse({"error": code}, status=status)


def receipt_response(receipt: ExternalEvidenceReceipt, *, created: bool) -> JsonResponse:
    return JsonResponse(
        {
            "status": "created" if created else "duplicate",
            "receipt_id": receipt.pk,
            "record_id": receipt.record_id,
        },
        status=201 if created else 200,
    )


@csrf_exempt
@require_POST
def receive_external_evidence(request: HttpRequest) -> JsonResponse:
    # This endpoint authenticates only a dedicated scoped credential, never session cookies.
    authorization = re.fullmatch(
        r"Bearer (titeni_[A-Za-z0-9_-]{43})",
        request.headers.get("Authorization", ""),
        flags=re.IGNORECASE | re.ASCII,
    )
    credential = None
    if authorization:
        credential = (
            EvidenceIntegration.objects.filter(
                token_digest=token_digest(authorization[1]),
                enabled=True,
                account__is_active=True,
            )
            .select_related("source")
            .first()
        )
    if credential is None:
        response = error_response("invalid_credentials", 401)
        response["WWW-Authenticate"] = "Bearer"
        return response
    if request.content_type != "application/json":
        return error_response("unsupported_media_type", 415)
    try:
        body = request.body
    except RequestDataTooBig:
        return error_response("payload_too_large", 413)
    if len(body) > MAX_PAYLOAD_BYTES:
        return error_response("payload_too_large", 413)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return error_response("invalid_json", 400)
    if not isinstance(payload, dict) or set(payload) - ExternalEvidenceForm.base_fields.keys():
        return error_response("invalid_fields", 400)
    if any(
        type(value) is not (int if name == "attempt_id" else str) for name, value in payload.items()
    ):
        return error_response("invalid_field_types", 400)
    try:
        for value in payload.values():
            if isinstance(value, str):
                value.encode("utf-8")
    except UnicodeEncodeError:
        return error_response("invalid_field_types", 400)
    form = ExternalEvidenceForm(payload)
    if not form.is_valid():
        return JsonResponse(
            {"error": "validation_failed", "fields": form.errors.get_json_data()}, status=400
        )
    data = form.cleaned_data
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = sha256(canonical.encode("ascii")).hexdigest()

    with transaction.atomic():
        # Lock the credential to make disabling or rotating it atomic with ingestion.
        current = (
            EvidenceIntegration.objects.select_for_update(of=("self",))
            .filter(
                pk=credential.pk,
                token_digest=credential.token_digest,
                enabled=True,
                account__is_active=True,
            )
            .first()
        )
        if current is None:
            response = error_response("invalid_credentials", 401)
            response["WWW-Authenticate"] = "Bearer"
            return response
        source = EvidenceSource.objects.select_for_update().get(pk=current.source_id)
        existing = ExternalEvidenceReceipt.objects.filter(
            source=source, external_id=data["external_id"]
        ).first()
        if existing is not None:
            if existing.payload_digest != digest:
                return error_response("external_id_conflict", 409)
            return receipt_response(existing, created=False)

        attempt = (
            AssessmentAttempt.objects.select_for_update(of=("self",))
            .filter(
                pk=data["attempt_id"],
                participation__event__component__version__blueprint__program_id=source.program_id,
                participation__enrollment__cohort__period__program_id=source.program_id,
            )
            .select_related("participation__event")
            .first()
        )
        if attempt is None:
            return error_response("attempt_not_found", 404)
        source_link = (
            BlueprintItemEvidenceSource.objects.select_for_update(of=("self",))
            .filter(
                item_id=attempt.participation.event.component_id,
                capability__source=source,
                capability__evidence_type__program_id=source.program_id,
                capability__evidence_type__code=data["evidence_type"],
            )
            .first()
        )
        if source_link is None:
            return error_response("source_not_linked", 422)
        if attempt.evidence_records.filter(
            source_link=source_link, reference=data["reference"]
        ).exists():
            return error_response("reference_conflict", 409)
        record = EvidenceRecord.objects.create(
            attempt=attempt,
            source_link=source_link,
            reference=data["reference"],
            context=data["context"],
            created_by_id=current.account_id,
        )
        receipt = ExternalEvidenceReceipt.objects.create(
            integration=current,
            source=source,
            record=record,
            external_id=data["external_id"],
            payload_digest=digest,
            adapter_version=ADAPTER_VERSION,
        )
        return receipt_response(receipt, created=True)
