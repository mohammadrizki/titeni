import pytest
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from apps.accounts.models import User


@pytest.mark.django_db
def test_glossary_is_available_to_any_signed_in_account(client: Client) -> None:
    url = reverse("glossary")
    assert client.get(url).status_code == 302
    assertNotContains(client.get(reverse("home")), f'href="{url}"')

    client.force_login(User.objects.create_user(username="pembaca-istilah"))
    response = client.get(url)
    assertContains(response, "Istilah di Titeni")
    assertContains(response, f'href="{url}" aria-current="page">Istilah</a>', count=2)
    assertContains(response, "<dt>Sintesis</dt>", html=True)
    assertContains(response, "<dt>Refleksi</dt>", html=True)
    assertContains(response, "<dt>Artefak</dt>", html=True)
    assertContains(response, '<a class="nav-link" href="#huruf-S"', count=1)
    assertContains(response, 'id="huruf-S"')
    terms = [term for _, group in response.context["term_groups"] for term, _ in group]
    assert terms == sorted(set(terms), key=str.casefold)
    assert client.post(url).status_code == 405
