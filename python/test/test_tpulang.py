#!/usr/bin/env python3
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================

import json
import numpy as np
import os, sys
import transform.TpuLang as tpul
from typing import List
import math

def is_int(dtype, width = None):
    if width == None:
        if is_int(dtype, 8) or is_int(dtype, 16) or is_int(dtype, 32) or is_int(dtype, 64):
            return True
    if width == 64 or width == 32 or width == 16 or width == 8:
        if dtype == 'int'+str(width) or dtype == 'uint'+str(width):
            return True
    return False

def is_fp(dtype, width = None):
    if width == None:
        if is_fp(dtype, 8) or is_fp(dtype, 16) or is_fp(dtype, 32) or is_fp(dtype, 64):
            return True
    if width == 64 or width == 32 or width == 20:
        if dtype == 'float'+str(width):
            return True
    if width == 8 and dtype in ['float8e5m2', 'float8e5m2fnuz', 'float8e4m3fn', 'float8e4m3fnuz']:
        return True
    if width == 16 and dtype in ['float16', 'bfloat16']:
        return True
    return False

def rand_data(shape, dtype, min=-10, max=10):
    if dtype in ['float32', 'float16']:
        return np.clip(np.random.randn(*shape).astype(dtype), min, max)
    if dtype == 'int32' or 'uint32' or 'int16' or 'uint16' or 'int8' or 'uint8':
        return np.random.randint(0, 256, size=shape).astype(dtype)
    raise Exception("Not supported data type: {}!".format(dtype))


def tpulang(chip):
    def wrapper(func):
        def decorate(*args, **kwargs):
            tpul.init(chip)
            func(*args, **kwargs)
            tpul.deinit()
        return decorate
    return wrapper


Failed_Cases = []

class TPULANG_IR_TESTER(object):
    ID = 0

    # This class is built for testing single operator transform.
    def __init__(self, chip: str = "bm1684x", mode: str = "all", simple: bool = False):
        Y, N = True, False
        self.test_function = {
            #############################
            # TpuLang Test Case, Alphabetically
            #############################
            # case:  (test,                    bm1684x_support, bm1688_support)
            "Abs": (self.test_Abs,                      Y, Y),
            "Add": (self.test_Add,                      Y, Y),
            "Arccos": (self.test_Arccos,                Y, Y),
            "Arctanh": (self.test_Arctanh,              Y, Y),
            "Arg": (self.test_Arg,                      Y, Y),
            # "Cast": (self.test_Cast,                    Y, Y),
            "Ceil": (self.test_Ceil,                    Y, Y),
            "Clamp": (self.test_Clamp,                  Y, Y),
            "Concat": (self.test_Concat,                Y, Y),
            "Conv2d": (self.test_Conv2d,                Y, Y),
            "Conv3d": (self.test_Conv3d,                Y, Y),
            # "Copy": (self.test_Copy,                    Y, Y), # only supports cv18xx
            "Cos": (self.test_Cos,                      Y, Y),
            "Cosh": (self.test_Cosh,                    Y, Y),
            "Deconv2d": (self.test_Deconv2d,            Y, Y),
            # "Deconv3d": (self.test_Deconv3d,            N, N), # not support
            "Div": (self.test_Div,                      Y, Y),
            "Elu": (self.test_Elu,                      Y, Y),
            "Eq": (self.test_Eq,                        Y, Y),
            "Eqs": (self.test_Eqs,                      Y, Y),
            "Erf": (self.test_Erf,                      Y, Y),
            "Exp": (self.test_Exp,                      Y, Y),
            "Floor": (self.test_Floor,                  Y, Y),
            "Gelu": (self.test_Gelu,                    Y, Y),
            "Ge": (self.test_Ge,                        Y, Y),
            "Ges": (self.test_Ges,                      Y, Y),
            "Gt": (self.test_Gt,                        Y, Y),
            "Gts": (self.test_Gts,                      Y, Y),
            "Hsigmoid": (self.test_Hsigmoid,            Y, Y),
            "Hswish": (self.test_Hswish,                Y, Y),
            # "Interpolate": (self.test_Interpolate,      Y, Y),
            "Le": (self.test_Le,                        Y, Y),
            "Les": (self.test_Les,                      Y, Y),
            "LeakyRelu": (self.test_LeakyRelu,          Y, Y),
            # "Lenet": (self.test_Lenet,                  N, N),
            "Lt": (self.test_Lt,                        Y, Y),
            "Lts": (self.test_Lts,                      Y, Y),
            "MatMul": (self.test_MatMul,                Y, Y),
            "Max": (self.test_Max,                      Y, Y),
            "Maxpool": (self.test_Maxpool,              Y, Y),
            "Ne": (self.test_Ne,                        Y, Y),
            "Nes": (self.test_Nes,                      Y, Y),
            "Min": (self.test_Min,                      Y, Y),
            "Mish": (self.test_Mish,                    Y, Y),
            "Mul": (self.test_Mul,                      Y, Y),
            "Pad": (self.test_Pad,                      Y, Y),
            "Permute": (self.test_Permute,              Y, Y),
            "Relu": (self.test_Relu,                    Y, Y),
            "Repeat": (self.test_Repeat,                Y, Y),
            "Reshape": (self.test_Reshape,              Y, Y),
            "Round": (self.test_Round,                  Y, Y),
            # "Rsqrt": (self.test_Rsqrt,                  Y, Y),
            "Shape_fetch": (self.test_Shape_fetch,      Y, Y),
            "Sign": (self.test_Sign,                    Y, Y),
            "Sigmoid": (self.test_Sigmoid,              Y, Y),
            "Sin": (self.test_Sin,                      Y, Y),
            "Sinh": (self.test_Sinh,                    Y, Y),
            "Softmax": (self.test_Softmax,              Y, Y),
            "Split": (self.test_Split,                  Y, Y),
            "Sqrt": (self.test_Sqrt,                    Y, Y),
            "Squeeze": (self.test_Squeeze,              Y, Y),
            "Sub": (self.test_Sub,                      Y, Y),
            "Tan": (self.test_Tan,                      Y, Y),
            "Tanh": (self.test_Tanh,                    Y, Y),
            "Tile": (self.test_Tile,                    Y, Y),
            #### model ####
            "HModel": (self.test_Model,                 N, N),
            "Resnet50":(self.test_Resnet50,             Y, Y),
            "ResnetBlock": (self.test_ResnetBlock,      Y, Y),
            "SelfAttnBlock": (self.test_SelfAttnBlock,  Y, Y),
            "MobilenetBlock": (self.test_MobilenetBlock,Y, Y),
        }
        # currently tpulang only supports fp quant mode
        self.support_quant_modes = ["f32", "f16", "bf16"]
        self.mode = mode.lower()
        self.simple = simple
        self.chip = chip.lower()
        if self.simple:
            self.support_quant_modes = ["f16"]
        if self.mode == "" or self.mode == "all":
            self.quant_modes = self.support_quant_modes
        else:
            if self.mode not in self.support_quant_modes:
                raise RuntimeError("{} not support mode: {}".format(self.chip, self.mode))
            self.quant_modes = [self.mode]

    def unique_name(self, name):
        name = "{}_{}".format(name, TPULANG_IR_TESTER.ID)
        TPULANG_IR_TESTER.ID += 1
        return name

    def test_single(self, case: str):
        np.random.seed(0)
        TPULANG_IR_TESTER.ID = 0
        print("Test: {}".format(case))
        if case in self.test_function:
            os.makedirs(case, exist_ok=True)
            os.chdir(case)
            func, _, _ = self.test_function[case]
            func(case)
            print("====== TEST {} Success ======".format(case))
        else:
            raise RuntimeError("case [{}] is not exist".format(case))

    def check_support(self, case):
        _, bm1684x_support, bm1688_support = self.test_function[case]
        if self.chip == "bm1684x" and bm1684x_support:
            return True
        if self.chip == "bm1688" and bm1688_support:
            return True
        return False

    def test_all(self):
        for case in self.test_function:
            if case not in Failed_Cases:
                self.test_single(case)
        print("====== ALL TEST Success ======".format(case))

    def list(self):
        print("====== All Support Ops ======")
        for case in self.test_function:
            if case not in Failed_Cases:
                print(case)
        print("====== Error Ops ======")
        for case in self.test_function:
            if case in Failed_Cases:
                print(case)

    def coeff_tensor(self, shape, dtype, data = None, scale=None, zero_point=None):
        if data is None:
            data = rand_data(shape, dtype)
            data = data * scale if (dtype == 'float32' and scale is not None) else data
        if dtype in ["int8", "uint8"]:
            return tpul.Tensor(dtype=dtype, shape=shape, data=data, ttype="coeff", scale=scale, zero_point=zero_point)
        else:
            return tpul.Tensor(dtype=dtype, shape=shape, data=data, ttype="coeff")

    def deploy(self, model_name, compare_all=False):
        in_f32_npz = model_name + '_in_f32.npz'
        top_out = model_name + '_top_outputs.npz'
        # deploy the model
        deploy_cmd_base = f"model_deploy.py --mlir {model_name}.mlir "
        deploy_cmd_base += "--chip {} ".format(self.chip)
        deploy_cmd_base += "--test_input {} ".format(in_f32_npz)
        deploy_cmd_base += "--test_reference {} ".format(top_out)
        if compare_all:
            deploy_cmd_base += "--compare_all "
        for mode in self.quant_modes:
            bmodel_name = "{}.bmodel".format(model_name + "_" + self.chip + "_" + mode)
            deploy_cmd = deploy_cmd_base
            deploy_cmd += "--model {} ".format(bmodel_name)
            deploy_cmd += "--quantize {} " .format(mode.upper())
            assert(os.system(deploy_cmd) == 0)

    def compile_and_check(self, model_name, inputs, outputs, mode=None):
        tpul.compile(model_name, inputs, outputs, True, False, mode=(mode if mode is not None else self.mode))
        # self.deploy(model_name, True)

    #######################################################################
    # Add
    # ------------
    def add_op(self, input_0, input_1, dtype="float32"):
        out_dtype = dtype if is_fp(dtype) else 'int32'
        add = tpul.add(input_0, input_1, out_dtype = out_dtype)
        return add

    def test_Add(self, case_name):
        """Add"""

        @tpulang(self.chip)
        def _test_add(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            add = self.add_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [add])

        @tpulang(self.chip)
        def _test_add_const(shape: List[int], value, is_reverse = False, dtype = "float32"):
            input = rand_data(shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape, data=input)
            add = self.add_op(value, x, dtype=dtype) if is_reverse else self.add_op(x, value, dtype=dtype)
            tpul.compile(self.unique_name(case_name), [x], [add], False, 2)

        _test_add([1, 3, 28, 28], [1, 3, 28, 28])
        # _test_add_const([1, 3, 28, 28], 3, False, "float16")
        # _test_add([1, 3, 28, 28], [1, 3, 28, 28], "float16")
        # _test_add([1, 3, 28, 28], [1, 3, 28, 28], "int32")
        _test_add([1, 3, 32, 32], [1, 3, 32, 32])
        _test_add([1, 3, 32, 32], [1, 1, 32, 32])
        _test_add([1, 3, 32, 32], [1])
        _test_add([1], [1, 3, 32, 32])

    #######################################################################
    # Convolution
    # ------------

    def conv3d_op(self,
                x,
                kshape,
                stride,
                pad=None,
                group=1,
                dilation=[1, 1, 1],
                zp=[None, None],
                bias=False,
                dtype="float32"):
        oc = kshape[0]
        weight = self.coeff_tensor(kshape, dtype)
        out_dtype = dtype if dtype == 'float32' else 'int32'
        bias = self.coeff_tensor(oc, out_dtype) if bias else None
        deconv = tpul.conv3d_v2(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            dilation=dilation,
                            group=group,
                            input_zp=zp[0],
                            weight_zp=zp[1],
                            out_dtype=out_dtype)
        return deconv

    def test_Conv3d(self, case_name):
        """Conv 3D"""

        @tpulang(self.chip)
        def _test_convolution(input_shape: List[int],
                              kernel_shape: List[int],
                              stride: List[int] = [1, 1, 1],
                              dilation: List[int] = [1, 1, 1],
                              pad: List[int] = None,
                              group=1,
                              dtype="float32",
                              zp: List[int] = [None, None]):
            x_data = rand_data(input_shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=input_shape, data=x_data)
            conv = self.conv3d_op(x,
                                kernel_shape,
                                stride,
                                pad,
                                group=group,
                                dilation=dilation,
                                zp=zp,
                                dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [conv])

        _test_convolution([1, 3, 28, 28, 28], [3, 1, 1, 1, 1], group=3)

 #######################################################################
    # Deconvolution
    # ------------
    def deconv_op(self,
                x,
                kshape,
                stride,
                pad=None,
                output_padding=None,
                group=1,
                dilation=[1, 1],
                zp=[None, None],
                bias=False,
                dtype="float32"):
        oc = kshape[0]
        weight = self.coeff_tensor(kshape, dtype)
        out_dtype = dtype if dtype == 'float32' else 'int32'
        bias = self.coeff_tensor(oc, out_dtype) if bias else None
        deconv = tpul.deconv_v2(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            output_padding=None,
                            dilation=dilation,
                            group=group,
                            input_zp=zp[0],
                            weight_zp=zp[1],
                            out_dtype=out_dtype)
        return deconv

    def deconv3d_op(self,
                x,
                kshape,
                stride,
                pad=None,
                output_padding=None,
                group=1,
                dilation=[1, 1, 1],
                zp=[None, None],
                bias=False,
                dtype="float32"):
        oc = kshape[0]
        weight = self.coeff_tensor(kshape, dtype)
        out_dtype = dtype if dtype == 'float32' else 'int32'
        bias = self.coeff_tensor(oc, out_dtype) if bias else None
        deconv = tpul.deconv3d_v2(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            output_padding=output_padding,
                            dilation=dilation,
                            group=group,
                            input_zp=zp[0],
                            weight_zp=zp[1],
                            out_dtype=out_dtype)
        return deconv

    def test_Deconv2d(self, case_name):
        """Deconv 2D"""

        @tpulang(self.chip)
        def _test_deconvolution(input_shape: List[int],
                              kernel_shape: List[int],
                              stride: List[int] = [1, 1],
                              dilation: List[int] = [1, 1],
                              pad: List[int] = None,
                              group=1,
                              dtype="float32",
                              zp: List[int] = [None, None]):
            x_data = rand_data(input_shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=input_shape, data=x_data)
            deconv = self.deconv_op(x,
                                kernel_shape,
                                stride,
                                pad,
                                group=group,
                                dilation=dilation,
                                zp=zp,
                                dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [deconv])

        _test_deconvolution([1, 3, 28, 28], [12, 3, 1, 1], group=3)
        _test_deconvolution([1, 3, 32, 32], [12, 3, 3, 3], stride=[2, 2], pad=[1, 1, 1, 1])

    def test_Deconv3d(self, case_name):
        """Deconv 3D"""

        @tpulang(self.chip)
        def _test_deconvolution(input_shape: List[int],
                              kernel_shape: List[int],
                              stride: List[int] = [1, 1, 1],
                              dilation: List[int] = [1, 1, 1],
                              pad: List[int] = None,
                              group=1,
                              dtype="float32",
                              zp: List[int] = [None, None]):
            x_data = rand_data(input_shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=input_shape, data=x_data)
            conv = self.deconv3d_op(x,
                                kernel_shape,
                                stride,
                                pad,
                                group=group,
                                dilation=dilation,
                                zp=zp,
                                dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [conv])

        _test_deconvolution([1, 3, 28, 28, 28], [3, 3, 1, 1, 1], group=3)

    #######################################################################
    # HModel
    # ------------
    def test_Model(self, case_name):

        def conv_quant(x, kshape, has_bias=False, stride=None, pad=None, group=1,
                       dilation=[1,1], scale=[1, 1], zp=[0, 0], dtype='int8'):
            oc = kshape[0]
            weight = self.coeff_tensor(kshape, dtype, scale=scale[0], zero_point=zp[0])
            out_dtype = dtype
            bias = self.coeff_tensor(oc, 'int32') if has_bias else None
            conv = tpul.conv_quant(x,
                                   weight,
                                   bias=bias,
                                   stride=stride,
                                   pad=pad,
                                   dilation=dilation,
                                   group=group,
                                   output_scale=scale[1],
                                   output_zp=zp[1],
                                   out_dtype=out_dtype)
            return conv

        def matmul_quant(left, right, has_bias=False, right_transpose=False, keep_dims=True,
                         scale=1, zp=0, dtype='int8'):
            bias = self.coeff_tensor(right.shape[-1], 'int32') if has_bias else None
            conv = tpul.matmul_quant(left,
                                     right=right,
                                     bias=bias,
                                     right_transpose=right_transpose,
                                     keep_dims=keep_dims,
                                     output_scale=scale,
                                     output_zp=zp,
                                     out_dtype=dtype)
            return conv

        def model_0(x):
            rq0 = tpul.requant_fp_to_int(x, 1.0, 0, 0, 'int8')
            kshape = [64, 3, 7, 7]
            data = rand_data(kshape, 'int8')
            weight0 = tpul.Tensor(dtype='int8', shape=kshape, data=data, is_const=True)
            data = rand_data(kshape[0], 'int32')
            bias1 = tpul.Tensor(dtype='int32', shape=kshape[0], data=data, is_const=True)

            conv1 = tpul.conv_v2(rq0, weight0, bias=bias1, stride=[2,2], pad=None, dilation=None,
                        group=1, input_zp=0, weight_zp=0, out_dtype='int32')
            # mul, shift = quantization(input_scale * weight_scale / output_scale)
            # https://tpumlir.org/docs/developer_manual/06_quantization.html
            rq1 = tpul.requant_int(conv1, 2030043136, -13, 0, 2, 'int8', round_mode='half_away_from_zero', out_name= 'conv1_name')
            return rq1

        def model_1(x):
            rq0 = tpul.requant_fp_to_int(x, 0.078125, 0, 0, 'int8')
            # mul, shift = affine_quantization(input_scale * weight_scale / output_scale)
            # tensorflow/lite/kernels/internal/quantization_utils.cc:QuantizeMultiplier()
            conv1 = conv_quant(rq0, [64,3,7,7], True, stride=[2,2], pad=[3,3,3,3], dilation=None,
                        group=1, scale=[0.078125, 0.078125], zp=[0, 0], dtype='int8')
            relu1 = tpul.relu(conv1)
            pool1 = tpul.maxpool(relu1, [3,3], stride=[2,2], pad=[1,1,1,1])
            conv2_1 = conv_quant(pool1, [64,64,1,1], True,
                        scale=[0.078125, 0.078125], zp=[0, 0], dtype='int8')
            relu2_1 = tpul.relu(conv2_1)
            conv2_2 = conv_quant(relu2_1, [64,64,3,3], True, pad=[1,1,1,1],
                        scale=[0.078125, 0.078125], zp=[0, 0], dtype='int8')
            relu2_2 = tpul.relu(conv2_2)
            conv2_3 = conv_quant(relu2_2, [256,64,1,1], True,
                        scale=[0.078125, 0.078125], zp=[0, 0], dtype='int8')
            conv2_0 = conv_quant(pool1, [256,64,1,1], True,
                        scale=[0.078125, 0.078125], zp=[0, 0], dtype='int8')
            add2 = tpul.add(conv2_3, conv2_0, out_scale=0.078125, out_dtype='int8')
            # dq29 = tpul.dequant_int_to_fp(add2, 0.0625, 0)
            return relu1

        def model_2(x):
            rq0 = tpul.requant_fp_to_int(x, 0.078125, 0, 0, 'int8')
            weight0 = self.coeff_tensor([128, 512], 'int8', scale=0.078125, zero_point=0)
            mat1 = matmul_quant(rq0, weight0, True, scale=0.078125, zp=0, dtype='int8')
            return mat1

        def model_3(x):
            rq0 = tpul.requant_fp_to_int(x, 0.078125, 0, 0, 'int8')
            weight0 = self.coeff_tensor([128, 512], 'int8')
            mat1 = self.matmul_op(rq0, weight0, None, izp=0, rzp=0, dtype='int32')
            rq2 = tpul.requant_int(mat1, 2030043136, -13, 0, 0, 'int8', round_mode='half_away_from_zero', out_name= 'conv1_name')
            return rq2

        def model_def(x):
            rq0 = tpul.requant_fp_to_int(x, 1.0, 0, 0, 'int8')
            conv1 = self.conv_op(rq0, [64, 3, 7, 7], [2, 2], None, zp=[0, 0], dtype='int8')
            rq2 = tpul.requant_int(conv1, 2030043136, -13, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu3 = tpul.relu(rq2)
            conv4 = self.conv_op(relu3, [96,64,3,3], [2,2], None, zp=[0,0], dtype='int8')
            rq5 = tpul.requant_int(conv4, 1748893696, -10, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu6 = tpul.relu(rq5)
            dq7 = tpul.dequant_int_to_fp(relu6, 0.25, 0)
            coeff8 = self.coeff_tensor([1,96,1,1], 'float32', scale=10.0)
            mul9 = tpul.mul(dq7, coeff8)
            coeff10 = self.coeff_tensor([1,96,1,1], 'float32', scale=-2.0)
            add11 = tpul.add(mul9, coeff10)
            relu12 = tpul.relu(add11)
            rq13 = tpul.requant_fp_to_int(relu12, 4.0, 0, 0, 'int8')
            conv14 = self.conv_op(rq13, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq15 = tpul.requant_int(conv14, 1623457792, -8, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu16 = tpul.relu(rq15)
            conv17 = self.conv_op(relu16, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq18 = tpul.requant_int(conv17, 1623457792, -10, 0, 0, 'int8', round_mode='half_away_from_zero')
            dq19 = tpul.dequant_int_to_fp(rq18, 0.0625, 0)
            add20 = tpul.add(dq19, dq7)
            coeff21 = self.coeff_tensor([1,96,1,1], 'float32', scale=2.0)
            mul22 = tpul.mul(add20, coeff21)
            coeff23 = self.coeff_tensor([1,96,1,1], 'float32', scale=-2.0)
            add24 = tpul.add(mul22, coeff23)
            relu25 = tpul.relu(add24)
            rq26 = tpul.requant_fp_to_int(relu25, 8.0, 0, 0, 'int8')
            conv27 = self.conv_op(rq26, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq28 = tpul.requant_int(conv27, 1712717824, -7, 0, 0, 'int8', round_mode='half_away_from_zero')
            dq29 = tpul.dequant_int_to_fp(rq28, 0.0625, 0)
            return dq29

        def model_def1(x):
            rq0 = tpul.requant_fp_to_int(x, 1.0, 0, 0, 'int8')
            conv1 = self.conv_op(rq0, [64, 3, 7, 7], [2, 2], None, zp=[0, 0], dtype='int8')
            rq2 = tpul.requant_int(conv1, 2030043136, -13, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu3 = tpul.relu(rq2)
            conv4 = self.conv_op(relu3, [96,64,3,3], [2,2], None, zp=[0,0], dtype='int8')
            rq5 = tpul.requant_int(conv4, 1748893696, -10, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu6 = tpul.relu(rq5)
            dq7 = tpul.dequant_int_to_fp(relu6, 0.25, 0)
            coeff8 = self.coeff_tensor([1,96,1,1], 'float32', scale=10.0)
            mul9 = tpul.mul(dq7, coeff8)
            coeff10 = self.coeff_tensor([1,96,1,1], 'float32', scale=-2.0)
            add11 = tpul.add(mul9, coeff10)
            relu12 = tpul.relu(add11)
            rq13 = tpul.requant_fp_to_int(relu12, 4.0, 0, 0, 'int8')
            conv14 = self.conv_op(rq13, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq15 = tpul.requant_int(conv14, 1623457792, -8, 0, 0, 'int8', round_mode='half_away_from_zero')
            relu16 = tpul.relu(rq15)
            conv17 = self.conv_op(relu16, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq18 = tpul.requant_int(conv17, 1623457792, -10, 0, 0, 'int8', round_mode='half_away_from_zero')
            dq19 = tpul.dequant_int_to_fp(rq18, 0.0625, 0)
            add20 = tpul.add(dq19, dq7)
            coeff21 = self.coeff_tensor([1,96,1,1], 'float32', scale=2.0)
            mul22 = tpul.mul(add20, coeff21)
            coeff23 = self.coeff_tensor([1,96,1,1], 'float32', scale=-2.0)
            add24 = tpul.add(mul22, coeff23)
            relu25 = tpul.relu(add24)
            rq26 = tpul.requant_fp_to_int(relu25, 8.0, 0, 0, 'int8')
            conv27 = self.conv_op(rq26, [96,96,3,3], [1,1], [1,1,1,1], zp=[0,0], dtype='int8')
            rq28 = tpul.requant_int(conv27, 1712717824, -7, 0, 0, 'int8', round_mode='half_away_from_zero')
            dq29 = tpul.dequant_int_to_fp(rq28, 0.0625, 0)
            return dq29

        @tpulang(self.chip)
        def _test_model_def(in_shape):
            x_data = rand_data(in_shape, 'float32', -10, 10)
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            # out = model_def(x=x)
            out = model_1(x=x)
            self.compile_and_check(self.unique_name(case_name), [x], [out], 'f32')

        _test_model_def([1, 3, 224, 224])

        @tpulang(self.chip)
        def _test_model2_def(in_shape):
            x_data = rand_data(in_shape, 'float32', -10, 10)
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            out = model_3(x=x)
            self.compile_and_check(self.unique_name(case_name), [x], [out], 'int8')

        # _test_model2_def([12, 384, 128])

    def test_Resnet50(self, case_name):
        def conv_block(x, kshape, stride, pad):
            conv = self.conv_op(x, kshape, stride, pad)
            norm = self.batch_norm_op(conv, kshape[0])
            relu = tpul.relu(norm)
            return relu

        def max_pool_block(x, oc, kshape, stride, pad):
            pool = tpul.maxpool(x, kernel=kshape, stride=stride, pad=pad)
            norm = self.batch_norm_op(pool, oc)
            relu = tpul.relu(norm)
            return relu

        def resnet_block0(x, oc, ic, kc, stride):
            conv0_0 = conv_block(x, [kc, ic, 1, 1], [1,1], [0,0,0,0])
            conv0_1 = conv_block(conv0_0, [kc, kc, 3, 3], [stride,stride], [1,1,1,1])
            conv0_2 = self.conv_op(conv0_1, [oc, kc, 1, 1], [1,1], [0,0,0,0])
            conv1 = self.conv_op(x, [oc, ic, 1, 1], [stride,stride], [0,0,0,0])
            return self.add_op(conv0_2, conv1)

        def resnet_block1(x, oc, kc):
            norm = self.batch_norm_op(x, oc)
            relu = tpul.relu(norm)
            conv0 = conv_block(relu, [kc, oc, 1, 1], [1,1], [0,0,0,0])
            conv1 = conv_block(conv0, [kc, kc, 3, 3], [1,1], [1,1,1,1])
            conv2 = self.conv_op(conv1, [oc, kc, 1, 1], [1,1], [0,0,0,0])
            return self.add_op(conv2, x)

        def resnet50(x):
            norm0 = self.batch_norm_op(x, 3)
            conv1 = conv_block(norm0, [64, 3, 7, 7], [2,2], [3,3,3,3])
            pool1 = max_pool_block(conv1, 64, [3,3], [2,2], [1,1,1,1])

            res2 = resnet_block0(pool1, 256, 64, 64, 1)
            res3 = resnet_block1(res2, 256, 64)
            res4 = resnet_block1(res3, 256, 64)
            norm4 = self.batch_norm_op(res4, 256)
            relu4 = tpul.relu(norm4)

            res5 = resnet_block0(relu4, 512, 256, 128, 2)
            res6 = resnet_block1(res5, 512, 128)
            res7 = resnet_block1(res6, 512, 128)
            res8 = resnet_block1(res7, 512, 128)
            norm8 = self.batch_norm_op(res8, 512)
            relu8 = tpul.relu(norm8)

            res9 = resnet_block0(relu8, 1024, 512, 256, 2)
            res10 = resnet_block1(res9, 1024, 256)
            res11 = resnet_block1(res10, 1024, 256)
            res12 = resnet_block1(res11, 1024, 256)
            res13 = resnet_block1(res12, 1024, 256)
            res14 = resnet_block1(res13, 1024, 256)
            norm14 = self.batch_norm_op(res14, 1024)
            relu14 = tpul.relu(norm14)

            res15 = resnet_block0(relu14, 2048, 1024, 512, 2)
            res16 = resnet_block1(res15, 2048, 512)
            res17 = resnet_block1(res16, 2048, 512)
            norm17 = self.batch_norm_op(res17, 2048)
            relu17 = tpul.relu(norm17)
            apool = tpul.avgpool(relu17, [7,7], [1,1], [0,0,0,0])
            reshape = tpul.reshape(apool, [0, -1])
            mat_weight = self.coeff_tensor([2048, 1000], "float32", scale=0.05)
            mat_bias = self.coeff_tensor([1000], "float32", scale=0.03)
            mat = self.matmul_op(reshape, mat_weight, mat_bias)
            return mat


        @tpulang(self.chip)
        def _test_model_def(in_shape):
            x_data = rand_data(in_shape, 'float32', -10, 10)
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            out = resnet50(x)
            self.compile_and_check(self.unique_name(case_name), [x], [out], 'f32')

        _test_model_def([1, 3, 224, 224])


    # def test_Resnet50_quant(self, case_name):
    #     def conv_block(x, kshape, stride, pad, zp):
    #         conv = self.conv_op(x, kshape, stride, pad, zp=zp, dtype='int8')
    #         rq = tpul.requant_int(conv, 2030043136, -13, 0, 0, 'int8', round_mode='half_away_from_zero')
    #         conv = self.conv_op(x, kshape, stride, pad)
    #         # norm = self.batch_norm_op(conv, kshape[0])
    #         relu = tpul.relu(conv)
    #         return relu

    #     def max_pool_block(x, oc, kshape, stride, pad):
    #         pool = tpul.maxpool(x, kernel=kshape, stride=stride, pad=pad)
    #         # norm = self.batch_norm_op(pool, oc)
    #         relu = tpul.relu(pool)
    #         return relu

    #     def resnet_block0(x, oc, ic, kc, stride):
    #         conv0_0 = conv_block(x, [kc, ic, 1, 1], [1,1], [0,0,0,0])
    #         conv0_1 = conv_block(conv0_0, [kc, kc, 3, 3], [stride,stride], [1,1,1,1])
    #         conv0_2 = self.conv_op(conv0_1, [oc, kc, 1, 1], [1,1], [0,0,0,0])
    #         conv1 = self.conv_op(x, [oc, ic, 1, 1], [stride,stride], [0,0,0,0])
    #         return self.add_op(conv0_2, conv1)

    #     def resnet_block1(x, oc, kc):
    #         # norm = self.batch_norm_op(x, oc)
    #         relu = tpul.relu(x)
    #         conv0 = conv_block(relu, [kc, oc, 1, 1], [1,1], [0,0,0,0])
    #         conv1 = conv_block(conv0, [kc, kc, 3, 3], [1,1], [1,1,1,1])
    #         conv2 = self.conv_op(conv1, [oc, kc, 1, 1], [1,1], [0,0,0,0])
    #         return self.add_op(conv2, x)

    #     def resnet50(x):
    #         norm0 = self.batch_norm_op(x, 3)
    #         conv1 = conv_block(norm0, [64, 3, 7, 7], [2,2], [3,3,3,3])
    #         pool1 = max_pool_block(conv1, 64, [3,3], [2,2], [1,1,1,1])

    #         res2 = resnet_block0(pool1, 256, 64, 64, 1)
    #         res3 = resnet_block1(res2, 256, 64)
    #         res4 = resnet_block1(res3, 256, 64)
    #         # norm4 = self.batch_norm_op(res4, 256)
    #         relu4 = tpul.relu(res4)

    #         res5 = resnet_block0(relu4, 512, 256, 128, 2)
    #         res6 = resnet_block1(res5, 512, 128)
    #         res7 = resnet_block1(res6, 512, 128)
    #         res8 = resnet_block1(res7, 512, 128)
    #         # norm8 = self.batch_norm_op(res8, 512)
    #         relu8 = tpul.relu(res8)

    #         res9 = resnet_block0(relu8, 1024, 512, 256, 2)
    #         res10 = resnet_block1(res9, 1024, 256)
    #         res11 = resnet_block1(res10, 1024, 256)
    #         res12 = resnet_block1(res11, 1024, 256)
    #         res13 = resnet_block1(res12, 1024, 256)
    #         res14 = resnet_block1(res13, 1024, 256)
    #         # norm14 = self.batch_norm_op(res14, 1024)
    #         relu14 = tpul.relu(res14)

    #         res15 = resnet_block0(relu14, 2048, 1024, 512, 2)
    #         res16 = resnet_block1(res15, 2048, 512)
    #         res17 = resnet_block1(res16, 2048, 512)
    #         # norm17 = self.batch_norm_op(res17, 2048)
    #         relu17 = tpul.relu(res17)
    #         apool = tpul.avgpool(relu17, [7,7], [1,1], [0,0,0,0])
    #         reshape = tpul.reshape(apool, [0, -1])
    #         mat_weight = self.coeff_tensor([2048, 1000], "float32", scale=0.05)
    #         mat_bias = self.coeff_tensor([1000], "float32", scale=0.03)
    #         mat = self.matmul_op(reshape, mat_weight, mat_bias)
    #         return mat


    #     @tpulang(self.chip)
    #     def _test_model_def(in_shape):
    #         x_data = rand_data(in_shape, 'float32', -10, 10)
    #         x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
    #         out = resnet50(x)
    #         self.compile_and_check(self.unique_name(case_name), [x], [out], 'f32')

    #     _test_model_def([1, 3, 224, 224])



    def batch_norm_op(self, x, oc):
        mean = self.coeff_tensor([oc], "float32", scale=0.2)
        var = self.coeff_tensor([oc], "float32", data=np.clip(np.random.randn(oc), 0.5, 10).astype(np.float32))
        gamma = self.coeff_tensor([oc], "float32", data=np.ones((oc)).astype(np.float32))
        beta = self.coeff_tensor([oc], "float32", data=np.zeros((oc)).astype(np.float32))
        return tpul.batch_norm(x, mean, var, gamma, beta)

    #######################################################################
    # Convolution
    # ------------
    def conv_op(self,
                x,
                kshape,
                stride,
                pad=None,
                group=1,
                dilation=[1, 1],
                bias=False,
                dtype="float32"):
        oc = kshape[0]
        weight = self.coeff_tensor(kshape, dtype, scale=1/(math.sqrt(kshape[1] * kshape[2] * kshape[3])))
        bias = self.coeff_tensor(oc, dtype) if bias else None
        conv = tpul.conv(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            dilation=dilation,
                            group=group,
                            out_dtype=dtype)
        return conv

    def test_Conv2d(self, case_name):
        """Conv 2D"""

        @tpulang(self.chip)
        def _test_convolution(input_shape: List[int],
                              kernel_shape: List[int],
                              stride: List[int] = [1, 1],
                              dilation: List[int] = [1, 1],
                              pad: List[int] = None,
                              group=1,
                              dtype="float32"):
            x_data = rand_data(input_shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=input_shape, data=x_data)
            conv = self.conv_op(x,
                                kernel_shape,
                                stride,
                                pad,
                                group=group,
                                dilation=dilation,
                                dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [conv])

        _test_convolution([1, 3, 28, 28], [12, 1, 1, 1], group=3)
        _test_convolution([1, 3, 32, 32], [12, 3, 3, 3], stride=[2, 2], pad=[0, 0, 1, 1])

    #######################################################################
    # Lenet
    # ------------
    def test_Lenet(self, case_name):

        def model_lenet(x):
            conv0 = self.conv_op(x, kshape=[32, 1, 5, 5], stride=[1,1], pad=[2, 2, 2, 2], dtype='float32')
            relu1 = self.relu_op(conv0)
            maxpool2 = self.maxpool_op(relu1, kshape=[2, 2], stride=[2, 2], pad=[0, 0, 0, 0])
            conv3 = self.conv_op(maxpool2, kshape=[64, 32, 5, 5], stride=[1,1], pad=[2, 2, 2, 2], dtype='float32')
            relu4 =  self.relu_op(conv3)
            maxpool5 =self.maxpool_op(relu4, kshape=[2, 2], stride=[2, 2], pad=[0, 0, 0, 0])
            conv6 = self.conv_op(maxpool5, kshape=[1024, 64, 7, 7], stride=[1,1], dtype='float32')
            relu7 =  self.relu_op(conv6)
            conv9 = self.conv_op(relu7,  kshape=[10, 1024, 1, 1], stride=[1,1], dtype='float32')
            return conv9

        @tpulang(self.chip)
        def _test_lenet(in_shape):
            x_data = (rand_data(in_shape, 'float32') - 0.5) * 256
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            out = model_lenet(x=x)
            self.compile_and_check(case_name, [x], [out])

        _test_lenet([1, 1, 28, 28])

    #######################################################################
    # Mul
    # ------------
    def mul_op(self, input_0, input_1, dtype="float32"):
        out_dtype = dtype if dtype == 'float32' else 'int32'
        mul = tpul.mul(input_0, input_1, out_dtype=out_dtype)
        return mul

    def test_Mul(self, case_name):
        """Mul"""

        @tpulang(self.chip)
        def _test_mul(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            mul = self.mul_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [mul])

        _test_mul([1, 3, 28, 28], [1, 3, 28, 28])
        _test_mul([1, 3, 32, 32], [1, 3, 32, 32])
        _test_mul([1, 3, 32, 32], [1, 1, 32, 32])
        _test_mul([1, 3, 32, 32], [1])
        _test_mul([1], [1, 3, 32, 32])

    #######################################################################
    # Sub
    # ------------
    def sub_op(self, input_0, input_1, dtype="float32"):
        out_dtype = dtype if dtype == 'float32' else 'int32'
        sub = tpul.sub(input_0, input_1, out_dtype=out_dtype)
        return sub

    def test_Sub(self, case_name):
        """Sub"""

        @tpulang(self.chip)
        def _test_sub(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            sub = self.sub_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [sub])

        _test_sub([1, 3, 28, 28], [1, 3, 28, 28])
        _test_sub([1, 3, 32, 32], [1, 3, 32, 32])
        _test_sub([1, 3, 32, 32], [1, 1, 32, 32])
        _test_sub([1, 3, 32, 32], [1])
        _test_sub([1], [1, 3, 32, 32])

    #######################################################################
    # Div
    # ------------
    def div_op(self, input_0, input_1):
        div = tpul.div(input_0, input_1)
        return div

    def test_Div(self, case_name):
        """Div"""

        @tpulang(self.chip)
        def _test_div(shape_x: List[int], shape_y: List[int]):
            x_data = rand_data(shape_x, "float32")
            y_data = rand_data(shape_y, "float32")
            x = tpul.Tensor(dtype="float32", shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype="float32", shape=shape_y, data=y_data)
            div = self.div_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x], [div])

        _test_div([1, 3, 28, 28], [1, 3, 28, 28])
        _test_div([1, 3, 32, 32], [1, 3, 32, 32])
        # _test_div([1, 3, 32, 32], [1, 1, 32, 32]) prob to be checked
        _test_div([1, 3, 32, 32], [1])
        _test_div([1], [1, 3, 32, 32])

    #######################################################################
    # Max
    # ------------
    def max_op(self, input_0, input_1, dtype="float32"):
        out_dtype = dtype if dtype == 'float32' else 'int32'
        max = tpul.max(input_0, input_1, out_dtype=out_dtype)
        return max

    def test_Max(self, case_name):
        """Max"""

        @tpulang(self.chip)
        def _test_max(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            max = self.max_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [max])

        _test_max([1, 3, 28, 28], [1, 3, 28, 28])
        _test_max([1, 3, 32, 32], [1, 3, 32, 32])
        _test_max([1, 3, 32, 32], [1, 1, 32, 32])
        _test_max([1, 3, 32, 32], [1])
        _test_max([1], [1, 3, 32, 32])

    #######################################################################
    # Min
    # ------------
    def min_op(self, input_0, input_1, dtype="float32"):
        out_dtype = dtype if dtype == 'float32' else 'int32'
        min = tpul.min(input_0, input_1, out_dtype=out_dtype)
        return min

    def test_Min(self, case_name):
        """Min"""

        @tpulang(self.chip)
        def _test_min(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            min = self.min_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [min])

        _test_min([1, 3, 28, 28], [1, 3, 28, 28])
        _test_min([1, 3, 32, 32], [1, 3, 32, 32])
        _test_min([1, 3, 32, 32], [1, 1, 32, 32])
        _test_min([1, 3, 32, 32], [1])
        _test_min([1], [1, 3, 32, 32])

    #######################################################################
    # Copy
    # ------------
    def copy_op(self, input):
        copy = tpul.copy(input)
        return copy

    def test_Copy(self, case_name):
        """Copy"""

        @tpulang(self.chip)
        def _test_copy(shape: List[int], dtype="float32"):
            x_data = rand_data(shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape, data=x_data)
            copy = self.copy_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [copy])

        _test_copy([1, 3, 28, 28])
        _test_copy([1, 3, 32, 32])

    # #######################################################################
    # # Cast
    # # ------------
    # def cast_op(self, input):
    #     cast = tpul.cast(input)
    #     return cast

    # def test_Cast(self, case_name):
    #     """Cast"""

    #     @tpulang(self.chip)
    #     def _test_cast(shape: List[int], dtype="float32"):
    #         x_data = rand_data(shape, dtype)
    #         x = tpul.Tensor(dtype=dtype, shape=shape, data=x_data)
    #         cast = self.cast_op(x)
    #         self.compile_and_check(self.unique_name(case_name), [x], [cast])

    #     _test_cast([1, 3, 28, 28], dtype="uint16")
    #     _test_cast([1, 3, 32, 32])

    #######################################################################
    # Clamp
    # ------------
    def clamp_op(self, input):
        clamp = tpul.clamp(input, -100., 100.)
        return clamp

    def test_Clamp(self, case_name):
        """Clamp"""

        @tpulang(self.chip)
        def _test_clamp(shape: List[int], dtype="float32"):
            x_data = rand_data(shape, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape, data=x_data)
            clamp = self.clamp_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [clamp])

        _test_clamp([1, 3, 28, 28])
        _test_clamp([1, 3, 32, 32])

    #######################################################################
    # Matmul
    # ------------
    def matmul_op(self, left, right, bias=None, izp=None, rzp=None, dtype="float32"):
        matmul = tpul.matmul(left, right, bias, input_zp=izp, right_zp=rzp, out_dtype=dtype)
        return matmul

    def test_MatMul(self, case_name):
        """Matmul"""

        @tpulang(self.chip)
        def _test_matmul(shape_x: List[int], shape_y: List[int], dtype="float32"):
            left = rand_data(shape_x, dtype)
            right = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=left)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=right)
            matmul = self.matmul_op(x, y, dtype=dtype)
            self.compile_and_check(self.unique_name(case_name), [x], [matmul])

        _test_matmul([1, 3, 28, 10], [1, 3, 10, 8])

    #######################################################################
    # Maxpool
    # ------------
    def maxpool_op(self,
                input_0,
                kshape,
                stride,
                pad=None,
                ceil_mode=False):
        maxpool = tpul.maxpool(input_0, kshape, stride, pad, ceil_mode)
        return maxpool

    def test_Maxpool(self, case_name):
        """Maxpool"""

        @tpulang(self.chip)
        def _test_maxpool(shape_x: List[int],
                                kshape: List[int] = [1,1],
                                stride: List[int] = [1, 1],
                                pad: List[int] = None,
                                dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            maxpool = self.maxpool_op(x, kshape, stride, pad)
            self.compile_and_check(self.unique_name(case_name), [x], [maxpool])

        _test_maxpool([1, 32, 28, 28], kshape = [2, 2], stride = [2, 2], pad=[0, 0, 0, 0])

    #######################################################################
    # Relu
    # ------------
    def relu_op(self, input):
        relu = tpul.relu(input)
        return relu

    def test_Relu(self, case_name):
        """Relu"""

        @tpulang(self.chip)
        def _test_relu(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            relu = self.relu_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [relu])

        _test_relu([1, 32, 28, 28])

    #######################################################################
    # LeakyRelu
    # ------------
    def leaky_relu_op(self, input):
        leaky_relu = tpul.leaky_relu(input)
        return leaky_relu

    def test_LeakyRelu(self, case_name):
        """LeakyRelu"""

        @tpulang(self.chip)
        def _test_leaky_relu(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            leaky_relu = self.leaky_relu_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [leaky_relu])

        _test_leaky_relu([1, 32, 28, 28])

    #######################################################################
    # Abs
    # ------------
    def abs_op(self, input):
        abs = tpul.abs(input)
        return abs

    def test_Abs(self, case_name):
        """Abs"""

        @tpulang(self.chip)
        def _test_abs(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            abs = self.abs_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [abs])

        _test_abs([1, 32, 28, 28])

    #######################################################################
    # Ceil
    # ------------
    def ceil_op(self, input):
        ceil = tpul.ceil(input)
        return ceil

    def test_Ceil(self, case_name):
        """Ceil"""

        @tpulang(self.chip)
        def _test_ceil(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            ceil = self.ceil_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [ceil])

        _test_ceil([1, 32, 28, 28])

    #######################################################################
    # Floor
    # ------------
    def floor_op(self, input):
        floor = tpul.floor(input)
        return floor

    def test_Floor(self, case_name):
        """Floor"""

        @tpulang(self.chip)
        def _test_floor(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            floor = self.floor_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [floor])

        _test_floor([1, 32, 28, 28])

    #######################################################################
    # Round
    # ------------
    def round_op(self, input):
        round = tpul.round(input)
        return round

    def test_Round(self, case_name):
        """Round"""

        @tpulang(self.chip)
        def _test_round(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            round = self.round_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [round])

        _test_round([1, 32, 28, 28])

    #######################################################################
    # Sin
    # ------------
    def sin_op(self, input):
        sin = tpul.sin(input)
        return sin

    def test_Sin(self, case_name):
        """sin"""

        @tpulang(self.chip)
        def _test_sin(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            sin = self.sin_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [sin])

        _test_sin([1, 32, 28, 28])

    #######################################################################
    # Cos
    # ------------
    def cos_op(self, input):
        cos = tpul.cos(input)
        return cos

    def test_Cos(self, case_name):
        """cos"""

        @tpulang(self.chip)
        def _test_cos(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            cos = self.cos_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [cos])

        _test_cos([1, 32, 28, 28])

    #######################################################################
    # Exp
    # ------------
    def exp_op(self, input):
        exp = tpul.exp(input)
        return exp

    def test_Exp(self, case_name):
        """exp"""

        @tpulang(self.chip)
        def _test_exp(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            exp = self.exp_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [exp])

        _test_exp([1, 32, 28, 28])

    #######################################################################
    # Tanh
    # ------------
    def tanh_op(self, input):
        tanh = tpul.tanh(input)
        return tanh

    def test_Tanh(self, case_name):
        """tanh"""

        @tpulang(self.chip)
        def _test_tanh(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            tanh = self.tanh_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [tanh])

        _test_tanh([1, 32, 28, 28])

    #######################################################################
    # Sigmoid
    # ------------
    def sigmoid_op(self, input):
        sigmoid = tpul.sigmoid(input)
        return sigmoid

    def test_Sigmoid(self, case_name):
        """sigmoid"""

        @tpulang(self.chip)
        def _test_sigmoid(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            sigmoid = self.sigmoid_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [sigmoid])

        _test_sigmoid([1, 32, 28, 28])

    #######################################################################
    # Elu
    # ------------
    def elu_op(self, input):
        elu = tpul.elu(input)
        return elu

    def test_Elu(self, case_name):
        """elu"""

        @tpulang(self.chip)
        def _test_elu(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            elu = self.elu_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [elu])

        _test_elu([1, 32, 28, 28])

    #######################################################################
    # Sqrt
    # ------------
    def sqrt_op(self, input):
        sqrt = tpul.sqrt(input)
        return sqrt

    def test_Sqrt(self, case_name):
        """sqrt"""

        @tpulang(self.chip)
        def _test_sqrt(shape_x: List[int], dtype="float32"):
            input = np.abs(rand_data(shape_x, dtype))
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            sqrt = self.sqrt_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [sqrt])

        _test_sqrt([1, 32, 28, 28])

    # #######################################################################
    # # Rsqrt
    # # ------------
    # def rsqrt_op(self, input):
    #     rsqrt = tpul.rsqrt(input)
    #     return rsqrt

    # def test_Rsqrt(self, case_name):
    #     """rsqrt"""

    #     @tpulang(self.chip)
    #     def _test_rsqrt(shape_x: List[int], dtype="float32"):
    #         input = np.abs(rand_data(shape_x, dtype))
    #         x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
    #         rsqrt = self.rsqrt_op(x)
    #         self.compile_and_check(self.unique_name(case_name), [x], [rsqrt])

    #     _test_rsqrt([1, 32, 28, 28])

    #######################################################################
    # Erf
    # ------------
    def erf_op(self, input):
        erf = tpul.erf(input)
        return erf

    def test_Erf(self, case_name):
        """erf"""

        @tpulang(self.chip)
        def _test_erf(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            erf = self.erf_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [erf])

        _test_erf([1, 32, 28, 28])

    #######################################################################
    # Tan
    # ------------
    def tan_op(self, input):
        tan = tpul.tan(input)
        return tan

    def test_Tan(self, case_name):
        """tan"""

        @tpulang(self.chip)
        def _test_tan(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            tan = self.tan_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [tan])

        _test_tan([1, 32, 28, 28])

    #######################################################################
    # Softmax
    # ------------
    def softmax_op(self, input, axis=0):
        softmax = tpul.softmax(input, axis=axis)
        return softmax

    def test_Softmax(self, case_name):
        """softmax"""

        @tpulang(self.chip)
        def _test_softmax(shape_x: List[int], axis: int, dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            softmax = self.softmax_op(x, axis)
            self.compile_and_check(self.unique_name(case_name), [x], [softmax])

        _test_softmax([1, 32, 28, 28], axis=1)

    #######################################################################
    # Mish
    # ------------
    def mish_op(self, input):
        mish = tpul.mish(input)
        return mish

    def test_Mish(self, case_name):
        """mish"""

        @tpulang(self.chip)
        def _test_mish(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            mish = self.mish_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [mish])

        _test_mish([1, 32, 28, 28])

    #######################################################################
    # Hswish
    # ------------
    def hswish_op(self, input):
        hswish = tpul.hswish(input)
        return hswish

    def test_Hswish(self, case_name):
        """hswish"""

        @tpulang(self.chip)
        def _test_hswish(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            hswish = self.hswish_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [hswish])

        _test_hswish([1, 32, 28, 28])

    #######################################################################
    # Arccos
    # ------------
    def arccos_op(self, input):
        arccos = tpul.arccos(input)
        return arccos

    def test_Arccos(self, case_name):
        """arccos"""

        @tpulang(self.chip)
        def _test_arccos(shape_x: List[int], dtype="float32"):
            input = np.clip(rand_data(shape_x, dtype), -0.99, 0.99)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            arccos = self.arccos_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [arccos])

        _test_arccos([1, 32, 28, 28])

    #######################################################################
    # Arctanh
    # ------------
    def arctanh_op(self, input):
        arctanh = tpul.arctanh(input)
        return arctanh

    def test_Arctanh(self, case_name):
        """arctanh"""

        @tpulang(self.chip)
        def _test_arctanh(shape_x: List[int], dtype="float32"):
            input = np.clip(rand_data(shape_x, dtype), -0.99, 0.99)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            arctanh = self.arctanh_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [arctanh])

        _test_arctanh([1, 32, 28, 28])

    #######################################################################
    # Sinh
    # ------------
    def sinh_op(self, input):
        sinh = tpul.sinh(input)
        return sinh

    def test_Sinh(self, case_name):
        """sinh"""

        @tpulang(self.chip)
        def _test_sinh(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            sinh = self.sinh_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [sinh])

        _test_sinh([1, 32, 28, 28])

    #######################################################################
    # Cosh
    # ------------
    def cosh_op(self, input):
        cosh = tpul.cosh(input)
        return cosh

    def test_Cosh(self, case_name):
        """cosh"""

        @tpulang(self.chip)
        def _test_cosh(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            cosh = self.cosh_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [cosh])

        _test_cosh([1, 32, 28, 28])

    #######################################################################
    # Sign
    # ------------
    def sign_op(self, input):
        sign = tpul.sign(input)
        return sign

    def test_Sign(self, case_name):
        """sign"""

        @tpulang(self.chip)
        def _test_sign(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            sign = self.sign_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [sign])

        _test_sign([1, 32, 28, 28])

    #######################################################################
    # Gelu
    # ------------
    def gelu_op(self, input):
        gelu = tpul.gelu(input)
        return gelu

    def test_Gelu(self, case_name):
        """gelu"""

        @tpulang(self.chip)
        def _test_gelu(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            gelu = self.gelu_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [gelu])

        _test_gelu([1, 32, 28, 28])

    #######################################################################
    # Hsigmoid
    # ------------
    def hsigmoid_op(self, input):
        hsigmoid = tpul.hsigmoid(input)
        return hsigmoid

    def test_Hsigmoid(self, case_name):
        """hsigmoid"""

        @tpulang(self.chip)
        def _test_hsigmoid(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            hsigmoid = self.hsigmoid_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [hsigmoid])

        _test_hsigmoid([1, 32, 28, 28])

    #######################################################################
    # Arg
    # ------------
    def arg_op(self, input):
        arg = tpul.arg(input)
        return arg

    def test_Arg(self, case_name):
        """arg"""

        @tpulang(self.chip)
        def _test_arg(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            arg1, arg2 = self.arg_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [arg1, arg2])

        _test_arg([1, 32, 28, 28])

    #######################################################################
    # Permute
    # ------------
    def permute_op(self, input):
        permute = tpul.permute(input, [0, 2, 3, 1])
        return permute

    def test_Permute(self, case_name):
        """permute"""

        @tpulang(self.chip)
        def _test_permute(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            permute = self.permute_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [permute])

        _test_permute([1, 1024, 10, 128])

    #######################################################################
    # Reshape
    # ------------
    def reshape_op(self, input):
        reshape = tpul.reshape(input, [32, 28, 1, 28])
        return reshape

    def test_Reshape(self, case_name):
        """reshape"""

        @tpulang(self.chip)
        def _test_reshape(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            reshape = self.reshape_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [reshape])

        _test_reshape([1, 32, 28, 28])

    #######################################################################
    # Shape_fetch
    # ------------
    def shape_fetch_op(self, input):
        shape_fetch = tpul.shape_fetch(input)
        return shape_fetch

    def test_Shape_fetch(self, case_name):
        """Shape_fetch"""

        @tpulang(self.chip)
        def _test_shape_fetch(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            shape_fetch = self.shape_fetch_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [shape_fetch])

        _test_shape_fetch([1, 32, 28, 28])

    #######################################################################
    # Squeeze
    # ------------
    def squeeze_op(self, input):
        squeeze = tpul.squeeze(input, [0])
        return squeeze

    def test_Squeeze(self, case_name):
        """squeeze"""

        @tpulang(self.chip)
        def _test_squeeze(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            squeeze = self.squeeze_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [squeeze])

        _test_squeeze([1, 32, 28, 28])

    #######################################################################
    # Pad
    # ------------
    def pad_op(self, input, pad_val=0.0, pad=None):
        pad_val = tpul.Scalar(pad_val)
        pad = tpul.pad(input, value=pad_val, padding=pad)
        return pad

    def test_Pad(self, case_name):
        """pad"""

        @tpulang(self.chip)
        def _test_pad(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            pad = self.pad_op(x, pad=[0, 0, 1, 2, 0, 0, 3, 4])
            self.compile_and_check(self.unique_name(case_name), [x], [pad])

        _test_pad([1, 32, 28, 28])

    #######################################################################
    # Tile
    # ------------
    def tile_op(self, input):
        tile = tpul.tile(input, [1,3,2,4])
        return tile

    def test_Tile(self, case_name):
        """tile"""

        @tpulang(self.chip)
        def _test_tile(shape_x: List[int], dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            tile = self.tile_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [tile])

        _test_tile([1, 32, 28, 28])

    #######################################################################
    # Concat
    # ------------
    def concat_op(self, input, axis=0):
        concat = tpul.concat(input, axis)
        return concat

    def test_Concat(self, case_name):
        """concat"""

        @tpulang(self.chip)
        def _test_concat(shapes: List[List[int]], dtype="float32"):
            input0 = rand_data(shapes[0], dtype)
            input1 = rand_data(shapes[1], dtype)

            x = tpul.Tensor(dtype=dtype, shape=shapes[0], data=input0)
            y = tpul.Tensor(dtype=dtype, shape=shapes[1], data=input1)
            concat = self.concat_op([x, y], axis=1)
            self.compile_and_check(self.unique_name(case_name), [x, y], [concat])

        _test_concat([[1, 32, 28, 28], [1, 2, 28, 28]])

    #######################################################################
    # Split
    # ------------
    def split_op(self, input, axis=0, num=1, size=None):
        split = tpul.split(input, axis=axis, num=num, size=size)
        return split

    def test_Split(self, case_name):
        """split"""

        @tpulang(self.chip)
        def _test_split(shape_x: List[int], axis=0, num=1, size=None, dtype="float32"):
            input = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=input)
            splits = self.split_op(x, axis, num, size)
            self.compile_and_check(self.unique_name(case_name), [x], splits)

        _test_split([1, 32, 28, 28], axis=1, num=2, size=[10, 22])

    #######################################################################
    # Repeat
    # ------------
    def repeat_op(self, input):
        reps = self.coeff_tensor(len(input.shape), "float32", data=np.random.randint(low=1, high=3,size=len(input.shape)).astype(np.float32))
        repeat = tpul.repeat(input, reps)
        return repeat

    def test_Repeat(self, case_name):
        """repeat"""

        @tpulang(self.chip)
        def _test_repeat(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            repeat = self.repeat_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [repeat])

        _test_repeat([1, 3, 28, 28])

    #######################################################################
    # Gt
    # ------------
    def gt_op(self, input_0, input_1):
        gt = tpul.gt(input_0, input_1)
        return gt

    def test_Gt(self, case_name):
        """Gt"""

        @tpulang(self.chip)
        def _test_gt(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            gt = self.gt_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [gt])

        _test_gt([1, 3, 28, 28], [1, 3, 28, 28])
        _test_gt([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Lt
    # ------------
    def lt_op(self, input_0, input_1):
        lt = tpul.lt(input_0, input_1)
        return lt

    def test_Lt(self, case_name):
        """Lt"""

        @tpulang(self.chip)
        def _test_lt(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            lt = self.lt_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [lt])

        _test_lt([1, 3, 28, 28], [1, 3, 28, 28])
        _test_lt([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Ge
    # ------------
    def ge_op(self, input_0, input_1):
        ge = tpul.ge(input_0, input_1)
        return ge

    def test_Ge(self, case_name):
        """Ge"""

        @tpulang(self.chip)
        def _test_ge(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            ge = self.ge_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [ge])

        _test_ge([1, 3, 28, 28], [1, 3, 28, 28])
        _test_ge([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Le
    # ------------
    def le_op(self, input_0, input_1):
        le = tpul.le(input_0, input_1)
        return le

    def test_Le(self, case_name):
        """Le"""

        @tpulang(self.chip)
        def _test_le(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            le = self.le_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [le])

        _test_le([1, 3, 28, 28], [1, 3, 28, 28])
        _test_le([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Eq
    # ------------
    def eq_op(self, input_0, input_1):
        eq = tpul.eq(input_0, input_1)
        return eq

    def test_Eq(self, case_name):
        """Eq"""

        @tpulang(self.chip)
        def _test_eq(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = np.random.randint(0, 256, size=shape_x).astype(np.float32)
            y_data = np.random.randint(0, 256, size=shape_x).astype(np.float32)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            eq = self.eq_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [eq])

        _test_eq([1, 3, 28, 28], [1, 3, 28, 28])
        _test_eq([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Ne
    # ------------
    def ne_op(self, input_0, input_1):
        ne = tpul.ne(input_0, input_1)
        return ne

    def test_Ne(self, case_name):
        """Ne"""

        @tpulang(self.chip)
        def _test_ne(shape_x: List[int], shape_y: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            y_data = rand_data(shape_y, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
            ne = self.ne_op(x, y)
            self.compile_and_check(self.unique_name(case_name), [x, y], [ne])

        _test_ne([1, 3, 28, 28], [1, 3, 28, 28])
        _test_ne([1, 3, 32, 32], [1, 3, 32, 32])

    #######################################################################
    # Gts
    # ------------
    def gts_op(self, input_0):
        gts = tpul.gts(input_0, 0)
        return gts

    def test_Gts(self, case_name):
        """Gts"""

        @tpulang(self.chip)
        def _test_gts(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            gts = self.gts_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [gts])

        _test_gts([1, 3, 32, 32])

    #######################################################################
    # Lts
    # ------------
    def lts_op(self, input_0):
        lts = tpul.lts(input_0, 0)
        return lts

    def test_Lts(self, case_name):
        """Lts"""

        @tpulang(self.chip)
        def _test_lts(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            lts = self.lts_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [lts])

        _test_lts([1, 3, 28, 28])
        _test_lts([1, 3, 32, 32])

    #######################################################################
    # Ges
    # ------------
    def ges_op(self, input_0):
        ges = tpul.ges(input_0, 0)
        return ges

    def test_Ges(self, case_name):
        """Ges"""

        @tpulang(self.chip)
        def _test_ges(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            ges = self.ges_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [ges])

        _test_ges([1, 3, 28, 28])
        _test_ges([1, 3, 32, 32])

    #######################################################################
    # Les
    # ------------
    def les_op(self, input_0):
        les = tpul.les(input_0, 0)
        return les

    def test_Les(self, case_name):
        """Les"""

        @tpulang(self.chip)
        def _test_les(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            les = self.les_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [les])

        _test_les([1, 3, 28, 28])
        _test_les([1, 3, 32, 32])

    #######################################################################
    # Eqs
    # ------------
    def eqs_op(self, input_0):
        eqs = tpul.eqs(input_0, 0)
        return eqs

    def test_Eqs(self, case_name):
        """Eqs"""

        @tpulang(self.chip)
        def _test_eqs(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            eqs = self.eqs_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [eqs])

        _test_eqs([1, 3, 28, 28])
        _test_eqs([1, 3, 32, 32])

    #######################################################################
    # Nes
    # ------------
    def nes_op(self, input_0):
        nes = tpul.nes(input_0, 0)
        return nes

    def test_Nes(self, case_name):
        """Nes"""

        @tpulang(self.chip)
        def _test_nes(shape_x: List[int], dtype="float32"):
            x_data = rand_data(shape_x, dtype)
            x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
            nes = self.nes_op(x)
            self.compile_and_check(self.unique_name(case_name), [x], [nes])

        _test_nes([1, 3, 28, 28])
        _test_nes([1, 3, 32, 32])

    #######################################################################
    # Resnet50 like model case
    # ------------
    def test_ResnetBlock(self, case_name):
        def conv_op(x,
                    kshape,
                    stride,
                    pad=None,
                    group=1,
                    dilation=[1, 1],
                    bias=False,
                    dtype="float32"):
            oc = kshape[0]
            weight = self.coeff_tensor(kshape, dtype)
            bias = self.coeff_tensor(oc, dtype) if bias else None
            conv = tpul.conv(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            dilation=dilation,
                            group=group)
            return conv

        # 1. define model
        def model_def(x):
            maxpool1 = tpul.maxpool(x, kernel=[3, 3], stride=[2, 2], pad=[1, 1, 1, 1])
            conv2 = conv_op(maxpool1, kshape=[64, 64, 1, 1], stride=[1, 1], dtype='float32')
            relu3 = tpul.relu(conv2)
            conv4 = conv_op(relu3, kshape=[64, 64, 3, 3], stride=[1, 1], pad=[1, 1, 1, 1], dtype='float32')
            relu5 =  tpul.relu(conv4)
            conv6 = conv_op(relu5, kshape=[256, 64, 1, 1], stride=[1, 1], dtype='float32')
            conv7 =  conv_op(maxpool1, kshape=[256, 64, 1, 1], stride=[1, 1], dtype='float32')
            add8 = tpul.add(conv6, conv7)
            relu9 = tpul.relu(add8)
            return relu9

        def _test_resnet_block(in_shape):
            # 2. prepare input
            x_data = rand_data(in_shape, 'float32')
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            # 3. init and compile tpulang model to top.mlir
            tpul.init(device=self.chip.upper())
            out = model_def(x)
            tpul.compile(case_name, [x], [out])
            tpul.deinit()
            # tpul.compile will do top mlir inference with random input
            in_f32_npz = case_name + '_in_f32.npz'
            top_out = case_name + '_top_outputs.npz'
            # 4. deploy to bmodel
            deploy_cmd_base = f"model_deploy.py --mlir {case_name}.mlir "
            deploy_cmd_base += "--chip {} ".format(self.chip)
            deploy_cmd_base += "--test_input {} ".format(in_f32_npz)
            deploy_cmd_base += "--test_reference {} ".format(top_out)
            # deploy to [f32, f16, bf16] quant mode
            for mode in self.quant_modes:
                bmodel_name = "{}.bmodel".format(case_name + "_" + self.chip + "_" + mode)
                deploy_cmd = deploy_cmd_base
                deploy_cmd += "--model {} ".format(bmodel_name)
                deploy_cmd += "--quantize {} " .format(mode.upper())
                assert(os.system(deploy_cmd) == 0)

        _test_resnet_block([1, 64, 112, 112])

    #######################################################################
    # Mobilenet like model case
    # ------------
    def test_MobilenetBlock(self, case_name):
        def conv_op(x,
                    kshape,
                    stride,
                    pad=None,
                    group=1,
                    dilation=[1, 1],
                    bias=False,
                    dtype="float32"):
            oc = kshape[0]
            weight = self.coeff_tensor(kshape, dtype)
            bias = self.coeff_tensor(oc, dtype) if bias else None
            conv = tpul.conv(x,
                            weight,
                            bias=bias,
                            stride=stride,
                            pad=pad,
                            dilation=dilation,
                            group=group)
            return conv

        # 1. model define
        class Model2():
            def __init__(self):
                super(Model2, self).__init__()
            def forward(self, input):
                conv0 = conv_op(input, kshape=[32, 1, 5, 5], stride=[1,1], pad=[2, 2, 2, 2], dtype='float32')
                relu1 = tpul.relu(conv0)
                maxpool2 = tpul.maxpool(relu1, kernel=[2, 2], stride=[2, 2], pad=[0, 0, 0, 0])
                conv3 = conv_op(maxpool2, kshape=[64, 32, 5, 5], stride=[1,1], pad=[2, 2, 2, 2], dtype='float32')
                relu4 =  tpul.relu(conv3)
                maxpool5 = tpul.maxpool(relu4, kernel=[2, 2], stride=[2, 2], pad=[0, 0, 0, 0])
                conv6 = conv_op(maxpool5, kshape=[1024, 64, 7, 7], stride=[1,1], dtype='float32')
                relu7 =  tpul.relu(conv6)
                softmax8 = tpul.softmax(relu7, axis=1)
                tpul.compile(case_name, [input], [softmax8])

        def _test_mobilenet_block(in_shape):
            # 2. prepare input
            x_data = rand_data(in_shape, 'float32')
            x = tpul.Tensor(dtype='float32', shape=in_shape, data=x_data)
            # 3. init and compile model to top.mlir
            tpul.init(device=self.chip.upper())
            model2 = Model2()
            model2.forward(x)
            # tpul.compile will do top mlir inference with random input
            in_f32_npz = case_name + '_in_f32.npz'
            top_out = case_name + '_top_outputs.npz'
            # 4. deploy to bmodel
            deploy_cmd_base = f"model_deploy.py --mlir {case_name}.mlir "
            deploy_cmd_base += "--chip {} ".format(self.chip)
            deploy_cmd_base += "--test_input {} ".format(in_f32_npz)
            deploy_cmd_base += "--test_reference {} ".format(top_out)
            for mode in self.quant_modes:
                bmodel_name = "{}.bmodel".format(case_name + "_" + self.chip + "_" + mode)
                deploy_cmd = deploy_cmd_base
                deploy_cmd += "--model {} ".format(bmodel_name)
                deploy_cmd += "--quantize {} " .format(mode.upper())
                assert(os.system(deploy_cmd) == 0)

        _test_mobilenet_block([1, 1, 28, 28])

    # #######################################################################
    # # Interpolate
    # # ------------
    # def interpolate_op(self, input):
    #     interpolate = tpul.interpolate(input, [1,2])
    #     return interpolate

    # def test_Interpolate(self, case_name):
    #     """interpolate"""

    #     @tpulang(self.chip)
    #     def _test_interpolate(shape_x: List[int], dtype="float32"):
    #         x_data = rand_data(shape_x, dtype)
    #         # y_data = rand_data(shape_y, dtype)
    #         x = tpul.Tensor(dtype=dtype, shape=shape_x, data=x_data)
    #         # y = tpul.Tensor(dtype=dtype, shape=shape_y, data=y_data)
    #         interpolate = self.interpolate_op(x)
    #         self.compile_and_check(self.unique_name(case_name), [x], [interpolate])

    #     _test_interpolate([1, 3, 28, 28])


    def test_SelfAttnBlock(self, case_name):
        class SelfAttnBlock():
            def __init__(self, batch, d, head, mq, mk):
                super(SelfAttnBlock, self).__init__()
                self.batch = batch
                self.d = d
                self.head = head
                self.mq = mq
                self.mk = mk

            def forward(self, q, k, v):
                permute_q = tpul.permute(q, [0, 2, 1, 3]) # 1, 10, 1024, 128
                permute_k = tpul.permute(k, [0, 2, 3, 1]) # 1, 10, 128, 1024
                mm0 = tpul.matmul(permute_q, permute_k)
                rsqrt0 = tpul.mul(mm0, tpul.Scalar(1 / np.sqrt(self.d), dtype=mm0.dtype))
                softmax0 = tpul.softmax(rsqrt0, axis=3)
                permute_v = tpul.permute(v, [0, 2, 1, 3])
                mm1 = tpul.matmul(softmax0, permute_v)
                permute_mm1 = tpul.permute(mm1, [0, 2, 1, 3])
                reshape_mm1 = tpul.reshape(permute_mm1, [self.batch, self.mq, self.head * self.d])

                tpul.compile(case_name, [q, k, v], [reshape_mm1])

        def _test_self_attn_block(batch, d, head, mq, mk):
            # 2. prepare input
            q_data = rand_data([batch, mq, head, d], 'float32')
            q = tpul.Tensor(dtype='float32', shape=[batch, mq, head, d], data=q_data) # 1, 1024, 10, 128
            k_data = rand_data([batch, mk, head, d], 'float32')
            k = tpul.Tensor(dtype='float32', shape=[batch, mq, head, d], data=k_data) # 1, 1024, 10, 128
            v_data = rand_data([batch, mk, head, d], 'float32')
            v = tpul.Tensor(dtype='float32', shape=[batch, mq, head, d], data=v_data) # 1, 1024, 10, 128
            # 3. init and compile tpulang model to top.mlir
            tpul.init(device=self.chip.upper())
            swint_block = SelfAttnBlock(batch, d, head, mq, mk)
            swint_block.forward(q, k, v)
            tpul.deinit()
            # tpul.compile will do top mlir inference with random input
            in_f32_npz = case_name + '_in_f32.npz'
            top_out = case_name + '_top_outputs.npz'
            # 4. deploy to bmodel
            deploy_cmd_base = f"model_deploy.py --mlir {case_name}.mlir "
            deploy_cmd_base += "--chip {} ".format(self.chip)
            deploy_cmd_base += "--test_input {} ".format(in_f32_npz)
            deploy_cmd_base += "--test_reference {} ".format(top_out)
            # deploy to [f32, f16, bf16] quant mode
            for mode in self.quant_modes:
                bmodel_name = "{}.bmodel".format(case_name + "_" + self.chip + "_" + mode)
                deploy_cmd = deploy_cmd_base
                deploy_cmd += "--model {} ".format(bmodel_name)
                deploy_cmd += "--quantize {} " .format(mode.upper())
                assert(os.system(deploy_cmd) == 0)

        _test_self_attn_block(1, 128, 10, 1024, 1024)

def test_one_case_in_all(tester: TPULANG_IR_TESTER, case, error_cases, success_cases):
    import traceback
    try:
        tester.test_single(case)
    except:
        error_cases.append(case)
        traceback.print_exc()
        return
    success_cases.append(case)

def test_all_base(tester: TPULANG_IR_TESTER):
    import multiprocessing
    from utils.misc import collect_process
    process_number = multiprocessing.cpu_count() // 2 + 1
    processes = []
    error_cases = multiprocessing.Manager().list()
    success_cases = multiprocessing.Manager().list()
    for case in tester.test_function:
        if tester.check_support(case):
            p = multiprocessing.Process(target=test_one_case_in_all,
                                        name=case,
                                        args=(tester, case, error_cases, success_cases))
            processes.append(p)
        if len(processes) == process_number:
            collect_process(processes, error_cases)
            processes = []
    collect_process(processes, error_cases)
    processes = []
    print("Success: {}".format(success_cases))
    print("Failure: {}".format(error_cases))
    if error_cases:
        print("====== test_tpulang.py --chip {} TEST Failed ======".format(tester.chip))
    else:
        print("====== test_tpulang.py --chip {} TEST Success ======".format(tester.chip))
    return error_cases, success_cases

def test_all(tester: TPULANG_IR_TESTER):
    f, s = test_all_base(tester)
    return f

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    # yapf: disable
    parser.add_argument("--chip", default="bm1684x", type=str,
                        choices=['bm1684x', 'bm1688'], help="chip platform name")
    parser.add_argument("--mode", default="all", type=str, choices=['all', 'f32', 'f16', 'bf16'], help="quantize modes, only supports fp for now")
    parser.add_argument("--simple", action="store_true", help='do simple test for commit test')
    parser.add_argument("--case", default="all", type=str, help="test one case, if all, then test all cases")
    parser.add_argument("--show_all", action="store_true", help='show all cases')
    parser.add_argument("--report", default="", type=str, help="report file name")
    # yapf: enable
    args = parser.parse_args()
    tester = TPULANG_IR_TESTER(args.chip, args.mode, args.simple)
    if args.show_all:
        print("====== Show All Cases ============")
        for case in tester.test_function:
            print(case)
        exit(0)
    dir = "tpulang_test_{}".format(args.chip)
    os.makedirs(dir, exist_ok=True)
    os.chdir(dir)
    if args.case == "" or args.case.lower() == "all":
        if args.report:
            f, s = test_all_base(tester)
        else:
            test_all(tester)
    else:
        tester.test_single(args.case)
    if args.report:
        result = {'succsess': list(s), 'failure': list(f)}
        with open(args.report, "w") as f:
            json.dump(result, f)
