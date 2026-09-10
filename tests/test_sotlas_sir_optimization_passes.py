"""Testes dos Passes de Otimização do SIR (Branch Folding e Redundant Load)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sotlas.sir.instructions import (
    SIRModule, SIRFunction, SIRBasicBlock, SIRValue,
    AllocStackInst, StoreInst, LoadInst, BranchInst, CondBranchInst, ReturnInst
)
from sotlas.sir.passes import (
    BranchFoldingPass, RedundantLoadPass, SIRPassManager
)


class TestSotlasSIROptimizationPasses(unittest.TestCase):

    def test_branch_folding_mesmo_destino(self):
        """Um cond_br com ambos os ramos apontando para o mesmo bloco colapsa para br."""
        mod = SIRModule(name="teste_branch")
        fn = SIRFunction(name="foo", parameters=[], return_type="void")
        b0 = fn.add_block("0")
        cond_val = SIRValue(name="cond", type_name="bool")
        # Ambos os ramos apontam para bb1
        b0.add(CondBranchInst(condition=cond_val, true_block="1", false_block="1"))
        b1 = fn.add_block("1")
        b1.add(ReturnInst())
        mod.add_function(fn)

        pass_inst = BranchFoldingPass()
        res = pass_inst.run(mod)
        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        self.assertIsInstance(b0.instructions[0], BranchInst)
        self.assertEqual(b0.instructions[0].target_block, "1")

    def test_branch_folding_trampolim(self):
        """Salto para bloco trampolim (que só contém outro salto) é redirecionado diretamente."""
        mod = SIRModule(name="teste_trampolim")
        fn = SIRFunction(name="bar", parameters=[], return_type="void")
        b0 = fn.add_block("0")
        b0.add(BranchInst(target_block="1"))
        
        # bb1 é trampolim para bb2
        b1 = fn.add_block("1")
        b1.add(BranchInst(target_block="2"))
        
        b2 = fn.add_block("2")
        b2.add(ReturnInst())
        mod.add_function(fn)

        pass_inst = BranchFoldingPass()
        res = pass_inst.run(mod)
        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        # b0 deve agora apontar diretamente para 2
        self.assertEqual(b0.instructions[0].target_block, "2")

    def test_redundant_load_pass(self):
        """Detecção de carga subsequente de variável recém armazenada."""
        mod = SIRModule(name="teste_load")
        fn = SIRFunction(name="baz", parameters=[], return_type="i32")
        b0 = fn.add_block("0")
        slot = SIRValue(name="slot_x", type_name="*mut i32")
        val1 = SIRValue(name="v1", type_name="i32")
        res_load = SIRValue(name="v2", type_name="i32")
        
        b0.add(AllocStackInst(var_name="x", type_name="i32", result=slot))
        b0.add(StoreInst(destination=slot, source=val1))
        b0.add(LoadInst(source=slot, result=res_load))
        b0.add(ReturnInst(value=res_load))
        mod.add_function(fn)

        pass_inst = RedundantLoadPass()
        res = pass_inst.run(mod)
        self.assertTrue(res.success)
        self.assertTrue(res.changed)

    def test_pass_manager_completo(self):
        """Executa todos os passes do SIRPassManager em pipeline completo."""
        mod = SIRModule(name="teste_pm")
        fn = SIRFunction(name="main", parameters=[], return_type="void")
        b0 = fn.add_block("0")
        b0.add(ReturnInst())
        # Código morto após o return
        b0.add(BranchInst(target_block="0"))
        mod.add_function(fn)

        pm = SIRPassManager()
        res = pm.run_all(mod)
        self.assertTrue(res.success)
        # Código morto foi eliminado pelo DeadCodeEliminationPass
        self.assertEqual(len(b0.instructions), 1)
        self.assertIsInstance(b0.instructions[0], ReturnInst)

    def test_unreachable_block_pass(self):
        """Blocos desconectados do bloco de entrada são podados com sucesso."""
        from sotlas.sir.passes import UnreachableBlockPass

        mod = SIRModule(name="teste_unreachable")
        fn = SIRFunction(name="detached_demo", parameters=[], return_type="void")
        b0 = fn.add_block("entry")
        b0.add(ReturnInst())

        # Bloco desconectado 'island' que nunca recebe saltos
        b_island = fn.add_block("island")
        b_island.add(ReturnInst())

        mod.add_function(fn)
        self.assertEqual(len(fn.blocks), 2)

        pass_inst = UnreachableBlockPass()
        res = pass_inst.run(mod)
        self.assertTrue(res.success)
        self.assertTrue(res.changed)
        self.assertEqual(len(fn.blocks), 1)
        self.assertEqual(fn.blocks[0].label, "entry")


if __name__ == "__main__":
    unittest.main()
