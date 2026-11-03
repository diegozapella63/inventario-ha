"""Valores e textos do servidor, um comportamento por teste: parse_value (formatos brasileiros, milhar, centavos,
R$, espaços, negativos, limites, número já numérico), text() (limite, obrigatório, tipos, espaços e quebras),
slug, fold, now_iso e stamp. Complementa test_basicos.py sem repetir os casos de lá."""
import re
import unittest
from datetime import datetime, timedelta
from unittest import mock

from _boot import UnitBase, server as S


class Relogio(datetime):
    """Relógio parado em 07/03/2026 09:05:03,123456 (hora local), para conferir os formatos de data."""

    @classmethod
    def now(cls, tz=None):
        fixo = datetime(2026, 3, 7, 9, 5, 3, 123456)
        return fixo if tz is None else fixo.astimezone(tz)


class ValorFormatos(UnitBase):
    def test_espaco_nao_separavel_entre_os_milhares(self):
        self.assertEqual(S.parse_value("1 200,50"), 1200.5, "o espaço que o Excel e o celular põem entre os milhares")

    def test_espaco_comum_entre_os_milhares(self):
        self.assertEqual(S.parse_value("1 200"), 1200)

    def test_cifrao_com_espacos_e_milhar_por_espaco(self):
        self.assertEqual(S.parse_value("R$ 1 234,56"), 1234.56)

    def test_tab_e_quebra_de_linha_nas_pontas(self):
        self.assertEqual(S.parse_value("\t300\n"), 300)

    def test_virgula_sem_parte_inteira(self):
        self.assertEqual(S.parse_value(",50"), 0.5)

    def test_milhar_com_uma_casa_decimal(self):
        self.assertEqual(S.parse_value("1.200,5"), 1200.5)

    def test_ponto_decimal_sem_milhar(self):
        self.assertEqual(S.parse_value("1200.50"), 1200.5, "com centavos depois do ponto, o ponto é decimal")

    def test_ponto_com_quatro_casas_nao_e_milhar(self):
        self.assertEqual(S.parse_value("1.2345"), 1.23, "só grupos de 3 dígitos contam como milhar")

    def test_pontos_fora_do_padrao_de_milhar_recusados(self):
        self.assertApiError(400, S.parse_value, "1.20.000")

    def test_numero_com_palavra_recusado(self):
        self.assertApiError(400, S.parse_value, "100 reais")

    def test_zero_com_centavos_vira_zero_inteiro(self):
        v = S.parse_value("0,00")
        self.assertEqual(v, 0)
        self.assertIsInstance(v, int)


class ValorArredondamento(UnitBase):
    def test_arredonda_para_centavos(self):
        self.assertEqual(S.parse_value(0.126), 0.13)

    def test_arredondado_sem_centavos_vira_inteiro(self):
        v = S.parse_value("2,999")
        self.assertEqual(v, 3)
        self.assertIsInstance(v, int)

    def test_menos_de_meio_centavo_vira_zero(self):
        self.assertEqual(S.parse_value(0.004), 0)

    def test_inteiro_continua_inteiro(self):
        v = S.parse_value(1500)
        self.assertEqual(v, 1500)
        self.assertIsInstance(v, int)

    def test_numero_com_centavos_continua_decimal(self):
        v = S.parse_value(10.5)
        self.assertEqual(v, 10.5)
        self.assertIsInstance(v, float)


class ValorLimites(UnitBase):
    def test_um_bilhao_e_aceito(self):
        self.assertEqual(S.parse_value(1_000_000_000), 1_000_000_000)

    def test_um_bilhao_escrito_com_milhar(self):
        self.assertEqual(S.parse_value("1.000.000.000"), 1_000_000_000)

    def test_um_centavo_acima_de_um_bilhao_recusado(self):
        self.assertApiError(400, S.parse_value, "1.000.000.000,01", msg_part="fora do intervalo")

    def test_negativo_diz_fora_do_intervalo(self):
        self.assertApiError(400, S.parse_value, "-5", msg_part="fora do intervalo")

    def test_infinito_recusado(self):
        for ruim in (float("inf"), "inf", "Infinity"):
            with self.subTest(ruim=ruim):
                self.assertApiError(400, S.parse_value, ruim)

    def test_texto_diz_como_escrever(self):
        self.assertApiError(400, S.parse_value, "caro", msg_part="1.200,50")

    def test_inteiro_enorme_recusado_com_400(self):
        self.assertApiError(400, S.parse_value, 10 ** 400, msg_part="fora do intervalo")


class Texto(UnitBase):
    def test_quebra_de_linha_do_meio_fica(self):
        self.assertEqual(S.text("linha 1\nlinha 2", 100, "detalhes"), "linha 1\nlinha 2")

    def test_quebras_e_tabs_das_pontas_saem(self):
        self.assertEqual(S.text("\n\t sofá \r\n", 100, "nome"), "sofá")

    def test_espaco_nao_separavel_das_pontas_sai(self):
        self.assertEqual(S.text(" sofá ", 100, "nome"), "sofá")

    def test_exatamente_no_limite_passa(self):
        self.assertEqual(S.text("x" * 10, 10, "nome"), "x" * 10)

    def test_limite_conta_depois_de_tirar_os_espacos(self):
        self.assertEqual(S.text("   " + "x" * 10 + "   ", 10, "nome"), "x" * 10)

    def test_letra_com_acento_conta_um_caractere(self):
        self.assertEqual(S.text("ção" * 10, 30, "nome"), "ção" * 10)

    def test_mensagem_de_limite_diz_o_campo(self):
        self.assertApiError(400, S.text, "x" * 5, 4, "detalhes", msg_part="O campo detalhes")

    def test_obrigatorio_sem_valor(self):
        self.assertApiError(400, S.text, None, 10, "nome", required=True, msg_part="Preencha o campo nome.")

    def test_vazio_sem_obrigatorio_devolve_vazio(self):
        self.assertEqual(S.text("", 10, "zona"), "")

    def test_zero_vira_texto_e_conta_como_preenchido(self):
        self.assertEqual(S.text(0, 10, "quantidade", required=True), "0")

    def test_numero_decimal_vira_texto(self):
        self.assertEqual(S.text(2.5, 10, "quantidade"), "2.5")


class Slug(UnitBase):
    def test_junta_separadores_seguidos(self):
        self.assertEqual(S.slug("Sala  --  de   estar"), "sala-de-estar")

    def test_tira_hifens_das_pontas(self):
        self.assertEqual(S.slug("--Varanda--"), "varanda")

    def test_mantem_numeros(self):
        self.assertEqual(S.slug("Quarto 2"), "quarto-2")

    def test_cedilha_e_til(self):
        self.assertEqual(S.slug("Coração Mãe"), "coracao-mae")

    def test_maiusculas_viram_minusculas(self):
        self.assertEqual(S.slug("LAVANDERIA"), "lavanderia")


class Fold(UnitBase):
    def test_iguala_acento_maiuscula_e_espacos_das_pontas(self):
        self.assertEqual({S.fold("Móveis"), S.fold("MOVEIS"), S.fold("  moveis ")}, {"moveis"})

    def test_mantem_os_espacos_do_meio(self):
        self.assertEqual(S.fold("Decoração  e arte"), "decoracao  e arte")

    def test_aceita_numero(self):
        self.assertEqual(S.fold(123), "123")

    def test_cedilha_vira_c(self):
        self.assertEqual(S.fold("Çç"), "cc")

    def test_ordinal_vira_letra(self):
        self.assertEqual(S.fold("Nº 1"), "no 1")


class Datas(UnitBase):
    ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_now_iso_tem_fuso_e_segundos(self):
        self.assertRegex(S.now_iso(), self.ISO)

    def test_now_iso_e_agora(self):
        quando = datetime.fromisoformat(S.now_iso())
        self.assertLess(abs(quando - datetime.now().astimezone()), timedelta(seconds=5))

    def test_now_iso_sem_microssegundos(self):
        with mock.patch.object(S, "datetime", Relogio):
            v = S.now_iso()
        self.assertTrue(v.startswith("2026-03-07T09:05:03"), v)
        self.assertNotIn(".123456", v)

    def test_stamp_formato(self):
        self.assertRegex(S.stamp(), r"^\d{4}-\d{2}-\d{2}-\d{4}$")

    def test_stamp_com_zeros_a_esquerda(self):
        with mock.patch.object(S, "datetime", Relogio):
            self.assertEqual(S.stamp(), "2026-03-07-0905")


if __name__ == "__main__":
    unittest.main()
