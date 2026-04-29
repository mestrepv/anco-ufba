"""
Adapters do django-allauth para o fluxo de autenticacao da AnCo.

- Valida dominio institucional do e-mail antes de criar conta via OAuth.
- Configura o User com `papel=leitor` por padrao.
"""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.shortcuts import render


def email_dominio_permitido(email: str, dominios_permitidos: list[str] | None = None) -> bool:
    """
    Devolve True se o dominio do e-mail bate com a allowlist.

    Itens da allowlist com ponto inicial (`.edu.br`) casam aquele sufixo,
    permitindo todas as instituicoes do TLD/SLD. Itens sem ponto inicial
    (`ufba.br`) casam exatamente aquele dominio ou um subdominio dele.

    Args:
        email: e-mail do usuario.
        dominios_permitidos: lista de strings; default usa
            settings.ALLOWED_INSTITUTIONAL_DOMAINS.
    """
    if not email or "@" not in email:
        return False
    if dominios_permitidos is None:
        dominios_permitidos = getattr(settings, "ALLOWED_INSTITUTIONAL_DOMAINS", [])

    dominio = email.rsplit("@", 1)[1].strip().lower()
    if not dominio:
        return False

    for padrao in dominios_permitidos:
        p = padrao.strip().lower()
        if not p:
            continue
        if p.startswith("."):
            # sufixo — casa o sufixo todo (.edu.br casa "usp.edu.br" e "lab.usp.edu.br")
            sufixo = p
            if dominio.endswith(sufixo):
                return True
            # tambem aceita "edu.br" como dominio exato (sem o ponto inicial)
            if dominio == sufixo[1:]:
                return True
        else:
            # dominio explicito ou subdominio dele
            if dominio == p or dominio.endswith("." + p):
                return True
    return False


class AnCoSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter de social login. Valida dominio antes de criar conta."""

    def pre_social_login(self, request, sociallogin):
        """
        Chamado pelo allauth apos o OAuth retornar com sucesso, antes de criar
        ou logar o User. Aqui rejeitamos dominios fora da lista institucional.
        """
        email = (sociallogin.user.email or "").strip().lower()
        if not email_dominio_permitido(email):
            response = render(
                request,
                "core/dominio_nao_autorizado.html",
                {"email": email},
                status=403,
            )
            raise ImmediateHttpResponse(response)
        # Dominio OK — allauth segue criando/conectando conta.

    def populate_user(self, request, sociallogin, data):
        """Garante que `papel=leitor` ao criar a conta via OAuth."""
        user = super().populate_user(request, sociallogin, data)
        # Por seguranca: novas contas via OAuth nascem como leitor (default ja eh leitor)
        if not user.papel:
            user.papel = user.Papel.LEITOR
        # Preenche nome_exibicao a partir do nome do Google se disponivel
        if not user.nome_exibicao:
            nome_google = (data.get("name") or "").strip() or user.get_full_name()
            user.nome_exibicao = nome_google[:200]
        return user


class AnCoAccountAdapter(DefaultAccountAdapter):
    """Adapter de conta padrao. Permite signup apenas via social login."""

    def is_open_for_signup(self, request) -> bool:
        # Cadastro publico desabilitado: a unica via eh OAuth.
        # Curadores podem criar contas manualmente pelo admin.
        return False
