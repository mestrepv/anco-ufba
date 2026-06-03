"""Forms do app core."""

from __future__ import annotations

from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile

User = get_user_model()


INSTITUICOES_PERMITIDAS = [
    ("IFBA", "IFBA — Instituto Federal da Bahia"),
    ("UFBA", "UFBA — Universidade Federal da Bahia"),
    ("UNEB", "UNEB — Universidade do Estado da Bahia"),
]


def _processar_foto(arquivo: UploadedFile, lado_max: int = 480) -> ContentFile:
    """
    Garante 1:1 e redimensiona para no máximo `lado_max` px.

    - Se o cliente já enviou recortada via Cropper.js (já é 1:1), só
      redimensiona e converte para JPEG.
    - Se chegou sem recorte (cliente sem JS / fallback), aplica crop
      centralizado.
    """
    from PIL import Image, ImageOps

    img = Image.open(arquivo)
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    # Fallback de crop centralizado quando não veio 1:1
    if img.width != img.height:
        lado = min(img.width, img.height)
        left = (img.width - lado) // 2
        top = (img.height - lado) // 2
        img = img.crop((left, top, left + lado, top + lado))
    if img.width > lado_max:
        img = img.resize((lado_max, lado_max), Image.LANCZOS)
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=88, optimize=True)
    nome_base = (arquivo.name or "foto").rsplit(".", 1)[0]
    return ContentFile(buffer.getvalue(), name=f"{nome_base}.jpg")


class PerfilForm(forms.ModelForm):
    """
    Perfil + solicitações em uma única tela.

    Campos do User: identidade, vínculo, identificadores.
    Campos virtuais (não persistem direto): `quer_ser_analista`,
    `quer_ser_revisor` e `justificativa` — disparam a criação de
    SolicitacaoCadastro tipo correspondente quando marcados.
    """

    vinculo_institucional = forms.ChoiceField(
        choices=[("", "— selecione —")] + INSTITUICOES_PERMITIDAS,
        required=False,
        label="Instituição",
    )

    quer_ser_analista = forms.BooleanField(
        required=False,
        label="Quero ser analista",
        help_text="Permite criar análises de artigos no acervo. Requer aprovação da curadoria.",
    )
    quer_ser_revisor = forms.BooleanField(
        required=False,
        label="Quero ser revisor",
        help_text="Permite ser sorteado para revisar análises por pares. Requer aprovação da curadoria e ser analista.",
    )

    class Meta:
        model = User
        fields = [
            "nome_exibicao",
            "foto",
            "vinculo_institucional",
            "orcid",
            "lattes_url",
        ]
        labels = {
            "nome_exibicao": "Nome de exibição",
            "foto": "Foto de perfil",
            "orcid": "ORCID",
            "lattes_url": "Currículo Lattes (URL)",
        }
        help_texts = {
            "nome_exibicao": "Como você aparece publicamente no acervo.",
            "foto": "Será recortada automaticamente em 1:1.",
            "orcid": "Formato 0000-0000-0000-000X.",
            "lattes_url": "URL completa do seu currículo na Plataforma Lattes.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-marca os checkboxes com o estado atual do usuário:
        # - já é analista OU tem solicitação ativa (pendente/aprovada) → marcado
        from .models import SolicitacaoCadastro

        user = self.instance
        if user and user.pk:
            self.fields["quer_ser_analista"].initial = (
                user.eh_analista
                or user.solicitacoes.filter(
                    tipo=SolicitacaoCadastro.Tipo.ANALISTA,
                    status__in=[
                        SolicitacaoCadastro.Status.PENDENTE,
                        SolicitacaoCadastro.Status.APROVADA,
                    ],
                ).exists()
            )
            self.fields["quer_ser_revisor"].initial = (
                user.revisor_aprovado
                or user.solicitacoes.filter(
                    tipo=SolicitacaoCadastro.Tipo.REVISOR,
                    status__in=[
                        SolicitacaoCadastro.Status.PENDENTE,
                        SolicitacaoCadastro.Status.APROVADA,
                    ],
                ).exists()
            )

    def save(self, commit=True):
        from .models import SolicitacaoCadastro

        instance = super().save(commit=False)
        # Foto nova: processa antes de persistir (cliente já mandou 1:1 via
        # Cropper.js; servidor faz fallback se chegou crua)
        foto = self.cleaned_data.get("foto")
        if isinstance(foto, UploadedFile):
            instance.foto = _processar_foto(foto)
        if commit:
            instance.save()
            self._sincronizar_solicitacoes(instance)
        return instance

    def _sincronizar_solicitacoes(self, user) -> None:
        """
        Cria SolicitacaoCadastro pendente para cada tipo marcado sem ativa.
        Não toca em solicitações existentes (pendentes ou aprovadas).
        """
        from .models import SolicitacaoCadastro

        para_criar = []
        for marcado, tipo, ja_tem_atributo in [
            (
                self.cleaned_data.get("quer_ser_analista"),
                SolicitacaoCadastro.Tipo.ANALISTA,
                "eh_analista",
            ),
            (
                self.cleaned_data.get("quer_ser_revisor"),
                SolicitacaoCadastro.Tipo.REVISOR,
                "revisor_aprovado",
            ),
        ]:
            if not marcado:
                continue
            # Pula se já tem o estado final ou solicitação ativa
            if getattr(user, ja_tem_atributo, False):
                continue
            if user.solicitacoes.filter(
                tipo=tipo,
                status__in=[
                    SolicitacaoCadastro.Status.PENDENTE,
                    SolicitacaoCadastro.Status.APROVADA,
                ],
            ).exists():
                continue
            para_criar.append(tipo)
        for tipo in para_criar:
            SolicitacaoCadastro.objects.create(
                usuario=user,
                tipo=tipo,
                justificativa="",
            )
