"""
Adapters do django-allauth para o fluxo de autenticacao da AnCo.

- Cadastro aberto: qualquer e-mail Google entra como `papel=leitor`.
- Vinculacao automatica por e-mail (evita conta duplicada).
- Promocao a analista exige aprovacao da curadoria via SolicitacaoCadastro.
"""

from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model


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
    """Adapter de social login.

    Cadastro aberto: qualquer e-mail Google pode criar conta. Toda nova
    conta nasce com `papel=leitor` (ver `populate_user`); a promoção a
    analista (e a habilitação como revisor) é controlada pelos curadores
    via aprovação no admin de SolicitacaoCadastro.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Vincula automaticamente a SocialAccount a um User existente com o
        mesmo e-mail (evita criar conta duplicada).
        """
        email = (sociallogin.user.email or "").strip().lower()
        # Vinculacao automatica por e-mail.
        # Se a SocialAccount ja existe (sociallogin.is_existing), allauth ja
        # sabe a quem conectar. Se nao existe, procuramos um User com mesmo
        # e-mail e ligamos a SocialAccount a ele.
        if sociallogin.is_existing or not email:
            return
        User = get_user_model()
        try:
            user_existente = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return  # nao existe: allauth criara novo User normalmente
        except User.MultipleObjectsReturned:
            return  # ambiguidade: deixa allauth decidir (criara novo)
        # Conecta a SocialAccount ao User existente — login segue como esse user.
        sociallogin.connect(request, user_existente)

    def is_open_for_signup(self, request, sociallogin) -> bool:
        """
        Cadastro via OAuth (Google) está aberto a qualquer e-mail. Quem entra
        vira `leitor` e precisa pedir promoção a analista.

        Sobrescreve a checagem do AccountAdapter, que para signup MANUAL
        (email/senha) continua fechado.
        """
        return True

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
