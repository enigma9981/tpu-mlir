# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================

from typing import Union, Iterable, List, Tuple, get_origin, get_args
from .MLIRImporter import MLIRImporter, State, Platform
from .BaseConverter import BaseConverter
from mlir.ir import *
import mlir.dialects.quant as quant
from utils.mlir_shell import *
import numpy as np


def _indent(sOrIt_: Union[str, Iterable], numSpaces: int) -> str:
    """Indent string"""
    if sOrIt_ is None:
        return "None"
    if isinstance(sOrIt_, str):
        s = sOrIt_.split("\n")
        if len(s) == 1:
            return sOrIt_
        s = [(numSpaces * " ") + line for line in s]
        return "\n".join(s)
    s = "\n".join([line.__repr__() for line in sOrIt_])
    return _indent(s, numSpaces)


def to_scalar(num):
    def wrapper(func):

        def __to_scalar(data):
            if isinstance(data, float):
                return Scalar(data, "float32")
            elif isinstance(data, int):
                return Scalar(data, "int32")
            return data

        def decorate(*args, **kwargs):
            need_to_scalar = False
            for idx, v in enumerate(args):
                if isinstance(v, Union[int, float]) and idx < num:
                    need_to_scalar = True
            if need_to_scalar:
                new_args = []
                for idx, v in enumerate(args):
                    if isinstance(v, Union[int, float]) and idx < num:
                        new_args.append(__to_scalar(v))
                    else:
                        new_args.append(v)
                return func(*new_args, **kwargs)
            else:
                return func(*args, **kwargs)

        return decorate
    return wrapper

def annotayion_check(func):

    def __type_instance(type0, type1):
        if get_origin(type1) is Union:
            ret = False
            for t in get_args(type1):
                ret = ret or __type_instance(type0, t)
            return ret
        if get_origin(type1) is list or get_origin(type1) is tuple:
            if not isinstance(type0, list) and not isinstance(type0, tuple):
                return False
            ret = True
            for i in range(len(type0)):
                ret = ret and isinstance(type0[i], get_args(type1))
            return ret
        else:
            return isinstance(type0, type1)

    def wrapper(*args, **kwargs):
        idx = 0
        for k, v in func.__annotations__.items():
            if idx >= len(args):
                if k in kwargs and kwargs[k] is None:
                    continue
                if k in kwargs and not __type_instance(kwargs[k], v):
                    print("function {} input type error, wish type: {}".format(func.__name__, func.__annotations__))
                    raise
            else:
                if args[idx] is None:
                    continue
                if not __type_instance(args[idx], v):
                    print("function {} input type error, wish type: {}".format(func.__name__, func.__annotations__))
                    raise
            idx += 1

        return func(*args, **kwargs)

    return wrapper

class Scalar:

    def __init__(self, value, dtype=None):
        self.value = value
        if dtype is None:
            self.dtype = 'float32'
        else:
            self.dtype = dtype

class Tensor:
    ID = 0

    def __init__(self,
                 shape: list = [],
                 name: str = None,
                 ttype="neuron",
                 data=None,
                 dtype: str = "float32",
                 scale: float = None,
                 zero_point: int = None):
        self.id = int(Tensor.ID)
        self.shape = shape if isinstance(shape, list) else [shape]
        self.name = "BMTensor" + str(self.id) if name is None else name
        assert ttype.lower() in ["neuron", "coeff"]
        self.ttype = ttype.lower()
        assert dtype.lower() in [
            "float32", "float16", "int32", "uint32", "int16", "uint16", "int8", "uint8"
        ]
        self.dtype = dtype.lower()
        if data is not None:
            assert data.dtype == self.dtype
        self.buffer = data
        self.is_quantized: bool = False
        self.quantization(scale=scale, zero_point=zero_point)
        Tensor.ID += 1

    def quantization(self,
                     scale: Union[float, List[float]] = None,
                     zero_point: Union[int, List[int]] = None):
        if self.is_quantized is False:
            self.is_quantized = scale is not None or zero_point is not None
            self.scale = scale
            self.zero_point = zero_point
        else:
            if self.scale is None:
                self.scale = scale
            elif scale is not None:
                assert self.scale == scale
            if self.zero_point is None:
                self.zero_point = zero_point
            elif zero_point is not None:
                assert self.zero_point == zero_point

    def __repr__(self):
        s = "tensor (\n{modstr}\n)"
        modstr = [self.id, self.name, self.shape, self.ttype, self.dtype, self.buffer]
        if self.is_quantized:
            modstr += [self.scale, self.zero_point]
        return s.format(modstr=_indent(modstr, 2))


class Operator:

    def __init__(self,
                 op_name: str,
                 inputs: List[Tensor],
                 outputs: List[Tensor],
                 params: dict = {}):
        self.op_name = op_name
        self.params = params
        self.inputs = inputs
        self.outputs = outputs

    def __repr__(self):
        s = "{type} (\n{modstr}\n)"
        modstr = "\n".join([
            "inputs (\n{}\n)".format(_indent(self.inputs, 2)),
            "outputs (\n{}\n)".format(_indent(self.outputs, 2)),
        ])
        return s.format(type=self.op_name, modstr=_indent(modstr, 2))


class Graph:

    def __init__(self, name="main"):
        self.name = name
        self.operators: List[Operator] = []
        self._inputs = None
        self._outputs = None

    @property
    def inputs(self):
        return self._inputs

    @inputs.setter
    def inputs(self, inputs: List[Tensor]):
        self._inputs = inputs

    @property
    def outputs(self):
        return self._outputs

    @outputs.setter
    def outputs(self, outputs: List[Tensor]):
        self._outputs = outputs

    def __repr__(self) -> str:
        s = "{name} (\n{modstr}\n)"
        modstr = "\n".join(["inputs (\n{}\n)".format(_indent(self.inputs, 2))] +
                           ["outputs (\n{}\n)".format(_indent(self.outputs, 2))] +
                           ["body (\n{}\n)".format(_indent(self.operators, 2))])
        return s.format(name=self.name, modstr=_indent(modstr, 2))


class TpuLangConverter(BaseConverter):
    MLIRImporterTypeStr = {
        "float64": "f64",
        "float32": "F32",
        "float16": "F16",
        "int8": "INT8",
        "int16": "INT16",
        "int32": "INT32",
        "int64": "INT64",
        "uint8": "UINT8",
        "uint16": "UINT16",
        "uint32": "UINT32",
        "uint64": "UINT64",
        "bool": "BOOL",
        "dict": "DICT",
    }

    def __init__(self, name: str, graph: Graph, mode: str):
        super().__init__()
        self.model_name = name
        self.model = graph
        self.load_model()
        state = State.TOP_QUANTIZED if mode != 'f32' and mode != 'all' else State.TOP_F32
        self.init_MLIRImporter(state)
        self.weight_file = self.mlir.weight_file
        self.constant = {}
        self.type_to_mlir = self.__type2mlir(self.mlir.ctx)
        for tensor in self.model.inputs:
            if tensor.is_quantized:
                self.input_types.append(self.get_quantized_type(tensor))
            else:
                self.input_types.append(self.MLIRImporterTypeStr[tensor.dtype])
        for tensor in self.model.outputs:
            if tensor.is_quantized:
                self.output_types.append(self.get_quantized_type(tensor))
            else:
                self.output_types.append(self.MLIRImporterTypeStr[tensor.dtype])
        self.mlir.declare_func(self.input_types, self.output_types)

    def __del__(self):
        if self.mlir != None:
            del self.mlir

    def load_model(self):
        self.num_input = len(self.model.inputs)
        self.input_types = []
        self.output_types = []
        for tensor in self.model.inputs:
            self.input_names.append(tensor.name)
            self.addShape(tensor.name, tensor.shape)
        for tensor in self.model.outputs:
            self.output_names.append(tensor.name)
            self.addShape(tensor.name, tensor.shape)

    def init_MLIRImporter(self, state:State):
        input_shapes = list()
        for _name in self.input_names:
            input_shapes.append(self.getShape(_name))
        output_shapes = list()
        for _name in self.output_names:
            if self.getShape(_name) != [1]:
                output_shapes.append(self.getShape(_name))
            else:
                output_shapes.append([])

        # init importer
        self.mlir = MLIRImporter(input_shapes,
                                 output_shapes,
                                 self.model_name,
                                 platform=Platform.TPULANG,
                                 state=state,
                                 do_declare=False)

    def __create_weight_op(self, tensor: Tensor):
        # constant variable/op
        tensor_type = self.__get_tensor_type(tensor)
        name_loc = Location.name(tensor.name)
        op = Operation.create("top.Weight", results=[tensor_type], loc=name_loc)
        self.mlir.insert_point.insert(op)
        self.constant[tensor.name] = tensor.buffer
        return op.results[0]

    def attr_to_mlir(self, params: dict):
        attrs = {}
        def _attr_convert(attr):
            if attr[2] is False:
                return self.mlir.ArrayAttr(attr[0], self.MLIRImporterTypeStr[attr[1]])
            elif attr[1].find("int") >= 0:
                return IntegerAttr.get(self.type_to_mlir[attr[1]], attr[0])
            elif attr[1] == "bool":
                return BoolAttr.get(attr[0])
            elif attr[1] == "string":
                return StringAttr.get(attr[0])
            else:
                return FloatAttr.get(self.type_to_mlir[attr[1]], attr[0])

        for key, value in params.items():
            # DictArrayAttr for custom op
            if value[1] == "dict" and not value[2]:
                array_attr = []
                for i, dict in enumerate(value[0]):
                    sub_dict = {}
                    for k, v in dict[0].items():
                        sub_dict[k] = _attr_convert(v)
                    dict_attr = DictAttr.get(sub_dict)
                    array_attr.append(dict_attr)
                attrs[key] = self.mlir.ArrayAttr(array_attr, self.MLIRImporterTypeStr[value[1]])
            else:
                attrs[key] = _attr_convert(value)
        return attrs

    def __type2mlir(self, mlir_ctx):
        return {
            "float64": F64Type.get(mlir_ctx),
            "float32": F32Type.get(mlir_ctx),
            "float16": F16Type.get(mlir_ctx),
            "int64": IntegerType.get_signless(64, mlir_ctx),
            "int32": IntegerType.get_signed(32, mlir_ctx),
            "int16": IntegerType.get_signed(16, mlir_ctx),
            "int8": IntegerType.get_signed(8, mlir_ctx),
            "uint32": IntegerType.get_unsigned(32, mlir_ctx),
            "uint16": IntegerType.get_unsigned(16, mlir_ctx),
            "uint8": IntegerType.get_unsigned(8, mlir_ctx),
            "bool": IntegerType.get_signless(1, mlir_ctx),
        }

    def get_quantized_type(self, tensor: Tensor):
        if tensor.is_quantized is False:
            raise ValueError("do not have quantized type")
        storage_type = self.type_to_mlir[tensor.dtype]
        # is_constant = tensor.buffer is not None
        is_signed = tensor.dtype == "int8" or tensor.dtype == "int16" or tensor.dtype == "int32"
        storage_min = (
            quant.QuantizedType.default_minimum_for_integer(  # type: ignore
                is_signed, storage_type.width))
        storage_max = quant.QuantizedType.default_maximum_for_integer(  # type: ignore
            is_signed, storage_type.width)
        flags = 1 if is_signed else 0
        scale = tensor.scale if tensor.scale is not None else 1.0
        zero_point = tensor.zero_point if tensor.zero_point is not None else 0
        is_perchannel = isinstance(scale, List) or isinstance(zero_point, List)
        if is_perchannel:
            length = len(scale) if isinstance(scale, List) else len(zero_point)
            return quant.UniformQuantizedPerAxisType.get(  # type: ignore
                flags, storage_type, self.type_to_mlir["float32"],
                scale if isinstance(scale, List) else [scale] * length,
                zero_point if isinstance(zero_point, List) else [zero_point] * length, 1,
                storage_min, storage_max)
        else:
            return quant.UniformQuantizedType.get(  # type: ignore
                flags, storage_type, self.type_to_mlir["float32"], scale, zero_point, storage_min,
                storage_max)

    def __get_tensor_type(self, tensor: Tensor):
        if tensor is None:
            self.type_to_mlir["float32"]
            output_shapes = []
        else:
            type = self.type_to_mlir[tensor.dtype]
            output_shapes = tensor.shape
        if tensor.is_quantized:
            type = self.get_quantized_type(tensor)
        if output_shapes == []:
            return UnrankedTensorType.get(type)
        if output_shapes is None:
            return NoneType.get()
        if isinstance(output_shapes, tuple):
            output_shapes = list(output_shapes)
        assert (isinstance(output_shapes, list))
        assert (len(output_shapes) > 0)
        if not isinstance(output_shapes[0], list) and output_shapes[0] is not None:
            return RankedTensorType.get(tuple(output_shapes), type)
        # multi output
        out_types = []
        for s in output_shapes:
            if s == []:
                out_types.append(UnrankedTensorType.get(type))
            elif s is None:
                out_types.append(NoneType.get())
            else:
                out_types.append(RankedTensorType.get(tuple(s), type))
        return out_types

    def convert_subgraph(self, subgraph: Graph):

        class symbolTable:
            symbol_table = {}

            def __init__(self, gen_value_func):
                self.gen_value_func = gen_value_func

            def __getitem__(self, tensor: Tensor):
                if tensor.id not in self.symbol_table:
                    if tensor.buffer is None:
                        raise Exception("Tensor '{}' is not constant!".format(tensor.name))
                    if tuple(tensor.shape) != tuple(tensor.buffer.shape):
                        raise Exception("Tensor shape is ambiguous! '{t_s}' vs '{b_s}'".format(
                            t_s=tensor.shape, b_s=tensor.buffer.shape))
                    op = self.gen_value_func(tensor)
                    self.symbol_table[tensor.id] = op
                    return op
                return self.symbol_table[tensor.id]

            def update(self, other):
                self.symbol_table.update(other)

        symbol_table = symbolTable(self.__create_weight_op)
        for idx, input in enumerate(subgraph.inputs):
            loc = Location.fused([Location.name(input.name)])
            input_op = self.mlir.create_input_op(loc, idx)
            symbol_table.update({input.id: input_op})

        def add_operation(operation: Operator):
            # get operation attributes
            attributes = self.attr_to_mlir(operation.params)
            # get input operands
            operands = []
            for tensor in operation.inputs:
                operands.append(symbol_table[tensor] if tensor is not None else self.mlir.none_op)
            rst_type = [self.__get_tensor_type(x) for x in operation.outputs]
            name_loc = Location.fused([Location.name(x.name) for x in operation.outputs])
            op = Operation.create(
                operation.op_name,
                results=rst_type,
                operands=operands,
                attributes=attributes,
                loc=name_loc,
            )
            self.mlir.insert_point.insert(op)
            symbol_table.update(dict(zip((x.id for x in operation.outputs), op.results)))

        return_op = []
        for op in subgraph.operators:
            add_operation(op)
            for out in op.outputs:
                if out.name in self.output_names:
                    return_op.append(symbol_table[out])

        return return_op

    def generate_mlir(self, mlir_file: str):
        return_op = self.convert_subgraph(self.model)
        self.mlir.create_return_op(return_op)
        mlir_txt = self.mlir.print_module()
        with open(mlir_file, "w") as f:
            f.write(mlir_txt)
        np.savez(self.weight_file, **self.constant)
        print("Save mlir file: {}".format(mlir_file))
