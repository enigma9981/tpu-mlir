import os
import unittest
import transform.TpuLang as tpul

def get_dtype_alisas(dtype):
    if dtype == 'float32':
        return 'f32'
    if dtype == 'float16':
        return 'f16'
    return None

class TestTPULangCustom(unittest.TestCase):
    def setUp(self):
        self.chip = os.getenv('CUSTOM_LAYER_CHIP_ARCH').upper()
        self.assertTrue(self.chip in ('BM1684X', 'BM1688'), "Unknown chip arch: {}".format(self.chip))
        tpul.init(self.chip)
        os.makedirs("tmp", exist_ok=True)
        os.chdir("tmp")
    def tearDown(self):
        os.chdir('..')
        tpul.deinit()
        # os.system('rm -r tmp')
    def compile(self, name:str, inputs:list, outputs:list, dtype:str):
        self.assertTrue(dtype in ('float32', 'float16'), "Unknown dtype: {}".format(dtype))
        tpul.compile(name, inputs, outputs, has_custom=True)
        deploy_cmd = "model_deploy.py --mlir {}.mlir --model {}.bmodel ".format(name, name)
        deploy_cmd += "--quantize {} --chip {}".format(get_dtype_alisas(dtype), self.chip)
        self.assertTrue(os.system(deploy_cmd) == 0, "Deploy fail")
