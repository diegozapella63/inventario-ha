"""1.54.0: Recursos. O pedido à IA (o produto, os detalhes, a página indicada), a limpeza do que ela responde (nomes
curtos sem repetir, no máximo 12, a fonte só com http) e as respostas fora do formato ou sem nada."""
import unittest
from unittest import mock

from _boot import UnitBase, server as S


class Pedido(UnitBase):
    def test_o_pedido_leva_o_produto_os_detalhes_e_a_pagina(self):
        p = S.rec_prompt("Cafeteira Oster", "Manual em https://fab.exemplo/manual.pdf")
        self.assertIn("Produto: Cafeteira Oster", p)
        self.assertIn("comece por https://fab.exemplo/manual.pdf", p)
        self.assertIn('"recursos"', p)
        self.assertNotIn("Detalhes:", S.rec_prompt("Cafeteira", ""))


class Limpeza(UnitBase):
    def test_nomes_curtos_sem_repetir_no_maximo_12_e_a_fonte(self):
        raw = {"produto": " TV  55 ", "recursos": ["HDR", {"nome": "hdr", "detalhe": "x"}, {"name": "Wi-Fi", "detail": "Rede"}, {"nome": ""}, 3]
               + [{"nome": f"R{i}"} for i in range(20)], "fonte": "https://fab.exemplo/tv"}
        r = S.rec_clean(raw)
        self.assertEqual(r["produto"], "TV 55")
        self.assertEqual([x["nome"] for x in r["recursos"]][:3], ["HDR", "Wi-Fi", "R0"])
        self.assertEqual(len(r["recursos"]), 12)
        self.assertEqual((r["fonte"], r["site"]), ("https://fab.exemplo/tv", "fab.exemplo"))
        self.assertEqual(S.rec_clean({"recursos": [], "fonte": "javascript:alert(1)"})["fonte"], "")
        self.assertEqual(S.rec_clean("nada")["recursos"], [])

    def test_a_ia_de_verdade_fora_do_formato_ou_sem_nada(self):
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value="não sei"):
            with self.assertRaises(S.ApiError) as e:
                S.ai_find_rec("TV", "", "ai_task.x")
            self.assertEqual(e.exception.status, 502)
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value='{"recursos": []}'):
            with self.assertRaises(S.ApiError) as e:
                S.ai_find_rec("TV", "", "ai_task.x")
            self.assertIn("marca e o modelo", e.exception.msg)
        with mock.patch.object(S, "AI_MOCK", False), mock.patch.object(S, "ai_call_text", return_value={"recursos": [{"nome": "Timer"}]}):
            self.assertEqual(S.ai_find_rec("TV", "", "ai_task.x")["recursos"], [{"nome": "Timer", "detalhe": ""}])


if __name__ == "__main__":
    unittest.main()
