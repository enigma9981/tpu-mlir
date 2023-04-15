//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// TPU-MLIR is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//

#include "tpu_mlir/Conversion/TopToTosa/OpLowering.h"

namespace tpu_mlir {

void populateTopToTosaConversionPatterns(RewritePatternSet *patterns) {
  patterns->add<
      // clang-format off
        InputLowering,
        AddLowering,
        ConvLowering,
        AvgPoolLowering,
        MaxPoolLowering,
        SoftmaxLowering
      // clang-format on
      >(patterns->getContext());
}

//===------------------------------------------------------------===//
// InputLowering
//===------------------------------------------------------------===//
void InputLowering::Lowering(PatternRewriter &rewriter, top::InputOp op) const {
  assert(op->getNumResults() == 1);
  auto outType = change_dataformat(op->getResult(0).getType());
  std::vector<Value> operands;
  operands.push_back(op->getOperand(0));
  std::vector<int32_t> perms = {0, 2, 3, 1};
  auto const_ty = RankedTensorType::get({4}, rewriter.getI32Type());
  DenseElementsAttr attr = DenseElementsAttr::get(
      const_ty, llvm::makeArrayRef(perms.data(), perms.size()));
  auto constop =
      rewriter.create<mlir::tosa::ConstOp>(op->getLoc(), const_ty, attr);
  operands.push_back(constop->getResult(0));
  rewriter.replaceOpWithNewOp<mlir::tosa::TransposeOp>(op, outType, operands);
}

//===------------------------------------------------------------===//
// AddLowering
//===------------------------------------------------------------===//
void AddLowering::Lowering(PatternRewriter &rewriter, top::AddOp op) const {
  assert(op->getNumResults() == 1);
  auto newType = change_dataformat(op->getResult(0).getType());
  auto coeff = op.getCoeffAttr();
  // TODO: coeff -> constOp
  /*
  if (!coeff) {
    float coeff0 = coeff.getValue()[0].cast<mlir::FloatAttr>().getValueAsDouble();

    auto const_ty = RankedTensorType::get({}, rewriter.getI32Type());
    DenseElementsAttr attr = DenseElementsAttr::get(const_ty,
                      llvm::makeArrayRef(perms.data(), perms.size()));
    auto constop = rewriter.create<mlir::tosa::ConstOp>(op->getLoc(), const_ty, attr);
    double coeff1 = coeff.getValue()[1].cast<mlir::FloatAttr>().getValueAsDouble();
  }
  */
  std::vector<Value> operands;
  for (auto in : op->getOperands()) {
    operands.push_back(in);
  }
  // do_relu
  if (op.getDoRelu()){
    // Add op
    auto add = rewriter.create<mlir::tosa::AddOp>(op->getLoc(), newType, operands);
    auto relu_limit = op.getReluLimit();
    std::vector<NamedAttribute> clamp_attr = gen_clamp_attr(rewriter, newType, relu_limit);
    auto out_type = add->getResult(0).getType();
    // Clamp op
    auto clamp = rewriter.create<mlir::tosa::ClampOp>(op->getLoc(), out_type,
                                 add->getResults(), clamp_attr);
    rewriter.replaceOp(op, clamp->getResults());
  } else {
    rewriter.replaceOpWithNewOp<mlir::tosa::AddOp>(op, newType, operands);
  }
}

//===------------------------------------------------------------===//
// ConvLowering
//===------------------------------------------------------------===//
void ConvLowering::Lowering(PatternRewriter &rewriter, top::ConvOp op) const {
  assert(op->getNumResults() == 1);
  auto newType = change_dataformat(op->getResult(0).getType());
  std::vector<NamedAttribute> attrs;
  auto x1 =
      op.getPadsAttr().getValue()[0].cast<mlir::IntegerAttr>().getInt(); // top
  auto x2 = op.getPadsAttr()
                .getValue()[2]
                .cast<mlir::IntegerAttr>()
                .getInt(); // bottom
  auto x3 =
      op.getPadsAttr().getValue()[1].cast<mlir::IntegerAttr>().getInt(); // left
  auto x4 = op.getPadsAttr()
                .getValue()[3]
                .cast<mlir::IntegerAttr>()
                .getInt(); // right
  std::vector<int64_t> newValues{x1, x2, x3, x4};
  attrs.push_back(
      rewriter.getNamedAttr("pad", rewriter.getI64ArrayAttr(newValues)));
  attrs.push_back(rewriter.getNamedAttr("stride", op.getStridesAttr()));
  attrs.push_back(rewriter.getNamedAttr("dilation", op.getDilationsAttr()));
  std::vector<Value> operands;
  auto ic = op->getOperand(0).getType().cast<RankedTensorType>().getShape()[1];
  auto oc = op->getResult(0).getType().cast<RankedTensorType>().getShape()[1];
  auto kc = op->getOperand(1).getType().cast<RankedTensorType>().getShape()[1];
  auto group = op.getGroup();
  // depth_wise conv
  if (ic == oc && oc ==group && kc == 1) {
    // auto weight = op->getOperand(1).getDefiningOp()->getResult(0);
    auto weight = op->getOperand(1);
    auto weightTy = weight.getType().cast<RankedTensorType>(); // NCHW
    // NCHW -> HWCM(HWCN)  In this case, "N"->"C", "C"="M"=1
    // std::vector<int32_t> perms = {2, 3, 0, 1};
    // NHWC -> HWCM(HWCN)  In this case, "N"->"C", "C"="M"=1
    std::vector<int32_t> perms = {1, 2, 0, 3};
    auto const_ty = RankedTensorType::get({4}, rewriter.getI32Type());
    DenseElementsAttr attr = DenseElementsAttr::get(const_ty,
                      llvm::makeArrayRef(perms.data(), perms.size()));
    auto constop = rewriter.create<mlir::tosa::ConstOp>(op->getLoc(), const_ty, attr);
    std::vector<int64_t> newWeightShape;
    auto weightShape = weightTy.getShape();       // NCHW
    newWeightShape.push_back(weightShape[2]);
    newWeightShape.push_back(weightShape[3]);
    newWeightShape.push_back(weightShape[0]);
    newWeightShape.push_back(weightShape[1]);     // HWCM(HWCN)
    auto newWeightTy = RankedTensorType::get(newWeightShape, weightTy.getElementType());
    auto newweight = rewriter.create<mlir::tosa::TransposeOp>(op->getLoc(), newWeightTy,
                                                  weight, constop->getResult(0))
                                                  -> getResult(0);
    operands.push_back(op->getOperand(0));
    operands.push_back(newweight);
    for (unsigned i = 2; i < op->getNumOperands(); i++){
      operands.push_back(op->getOperand(i));
    }
    // do_relu
    if (op.getDoRelu()) {
      // Conv op
      auto conv = rewriter.create<mlir::tosa::DepthwiseConv2DOp>(
                           op->getLoc(), newType, operands, attrs);
      auto relu_limit = op.getReluLimit();
      std::vector<NamedAttribute> clamp_attr = gen_clamp_attr(rewriter, newType, relu_limit);
      auto out_type = conv->getResult(0).getType();
      // Clamp op
      auto clamp = rewriter.create<mlir::tosa::ClampOp>(op->getLoc(), out_type,
                                   conv->getResults(), clamp_attr);
      rewriter.replaceOp(op, clamp->getResults());
    } else {
      rewriter.replaceOpWithNewOp<mlir::tosa::DepthwiseConv2DOp>(
                                     op, newType, operands, attrs);
    }
  }
  // normal conv
  else if (group == 1) {
    for (auto in : op->getOperands()) {
      operands.push_back(in);
    }
    // do_Relu
    if (op.getDoRelu()) {
      // Conv op
      auto conv = rewriter.create<mlir::tosa::Conv2DOp>(op->getLoc(), newType, operands, attrs);
      auto relu_limit = op.getReluLimit();
      std::vector<NamedAttribute> clamp_attr = gen_clamp_attr(rewriter, newType, relu_limit);
      auto out_type = conv->getResult(0).getType();
      // Clamp op
      auto clamp = rewriter.create<mlir::tosa::ClampOp>(op->getLoc(), out_type,
                                   conv->getResults(), clamp_attr);
      rewriter.replaceOp(op, clamp->getResults());
    } else {
      rewriter.replaceOpWithNewOp<mlir::tosa::Conv2DOp>(op, newType, operands, attrs);
    }
  }
  //TODO: support for group conv
  else ;
}

//===------------------------------------------------------------===//
// AvgPoolLowering
//===------------------------------------------------------------===//
void AvgPoolLowering::Lowering(PatternRewriter &rewriter,
                               top::AvgPoolOp op) const {
  assert(op->getNumResults() == 1);
  auto newType = change_dataformat(op->getResult(0).getType());
  std::vector<Value> operands;
  for (auto in : op->getOperands()) {
    operands.push_back(in);
  }
  std::vector<NamedAttribute> attrs;
  attrs.push_back(rewriter.getNamedAttr("kernel", op.getKernelShapeAttr()));
  attrs.push_back(rewriter.getNamedAttr("stride", op.getStridesAttr()));
  auto x1 =
      op.getPadsAttr().getValue()[0].cast<mlir::IntegerAttr>().getInt(); // top
  auto x2 = op.getPadsAttr()
                .getValue()[2]
                .cast<mlir::IntegerAttr>()
                .getInt(); // bottom
  auto x3 =
      op.getPadsAttr().getValue()[1].cast<mlir::IntegerAttr>().getInt(); // left
  auto x4 = op.getPadsAttr()
                .getValue()[3]
                .cast<mlir::IntegerAttr>()
                .getInt(); // right
  std::vector<int64_t> newValues{x1, x2, x3, x4};
  attrs.push_back(
      rewriter.getNamedAttr("pad", rewriter.getI64ArrayAttr(newValues)));
  // do_relu
  if (op.getDoRelu()) {
    // Avgpool op
    auto avgpool = rewriter.create<mlir::tosa::AvgPool2dOp>(
                      op->getLoc(), newType, operands, attrs);
    auto relu_limit = op.getReluLimit();
    std::vector<NamedAttribute> clamp_attr = gen_clamp_attr(rewriter, newType, relu_limit);
    auto out_type = avgpool->getResult(0).getType();
    // Clamp op
    auto clamp = rewriter.create<mlir::tosa::ClampOp>(op->getLoc(), out_type,
                                 avgpool->getResults(), clamp_attr);
    rewriter.replaceOp(op, clamp->getResults());
  } else {
    rewriter.replaceOpWithNewOp<mlir::tosa::AvgPool2dOp>(
                             op, newType, operands, attrs);
  }
}

//===------------------------------------------------------------===//
// MaxPoolLowering
//===------------------------------------------------------------===//
void MaxPoolLowering::Lowering(PatternRewriter &rewriter,
                               top::MaxPoolOp op) const {
  assert(op->getNumResults() == 1);
  auto newType = change_dataformat(op->getResult(0).getType());
  std::vector<Value> operands;
  for (auto in : op->getOperands()) {
    operands.push_back(in);
  }
  std::vector<NamedAttribute> attrs;
  attrs.push_back(rewriter.getNamedAttr("kernel", op.getKernelShapeAttr()));
  attrs.push_back(rewriter.getNamedAttr("stride", op.getStridesAttr()));
  auto x1 =
      op.getPadsAttr().getValue()[0].cast<mlir::IntegerAttr>().getInt(); // top
  auto x2 = op.getPadsAttr()
                .getValue()[2]
                .cast<mlir::IntegerAttr>()
                .getInt(); // bottom
  auto x3 =
      op.getPadsAttr().getValue()[1].cast<mlir::IntegerAttr>().getInt(); // left
  auto x4 = op.getPadsAttr()
                .getValue()[3]
                .cast<mlir::IntegerAttr>()
                .getInt(); // right
  std::vector<int64_t> newValues{x1, x2, x3, x4};
  attrs.push_back(
      rewriter.getNamedAttr("pad", rewriter.getI64ArrayAttr(newValues)));
  // do_relu
  if (op.getDoRelu()) {
    // Maxpool op
    auto maxpool = rewriter.create<mlir::tosa::MaxPool2dOp>(
                      op->getLoc(), newType, operands, attrs);
    auto relu_limit = op.getReluLimit();
    std::vector<NamedAttribute> clamp_attr = gen_clamp_attr(rewriter, newType, relu_limit);
    auto out_type = maxpool->getResult(0).getType();
    // Clamp op
    auto clamp = rewriter.create<mlir::tosa::ClampOp>(op->getLoc(), out_type,
                                 maxpool->getResults(), clamp_attr);
    rewriter.replaceOp(op, clamp->getResults());
  } else {
    rewriter.replaceOpWithNewOp<mlir::tosa::MaxPool2dOp>(
                             op, newType, operands, attrs);
  }
}

//===------------------------------------------------------------===//
// SoftmaxLowering
//===------------------------------------------------------------===//
void SoftmaxLowering::Lowering(PatternRewriter &rewriter,
                               top::SoftmaxOp op) const {
  assert(op->getNumResults() == 1);
  auto preType = op->getResult(0).getType();
  auto newType = change_dataformat(preType);
  auto size = preType.cast<RankedTensorType>().getShape().size();
  int32_t new_axis, axis = op.getAxis();
  if(size == 4) {
    if (axis == 1 || axis == -3) new_axis = 3;       // C
    else if (axis == 2 || axis == -2) new_axis = 1;  // H
    else if (axis == 3 || axis == -1) new_axis = 2;  // W
    else new_axis = axis;                            // N
  }
  bool log_attr_val = op.getLog();
  // op.getBeta() (beta = 1 by default)
  // ReduceMaxOp
  std::vector<NamedAttribute> attrs;
  attrs.push_back(
      rewriter.getNamedAttr("axis", rewriter.getI64IntegerAttr(new_axis)));
  std::vector<int64_t> out_shape(newType.cast<RankedTensorType>().getShape());
  out_shape[new_axis] = 1;
  auto out_type = RankedTensorType::get(out_shape, newType.cast<RankedTensorType>().getElementType());
  auto reducemax = rewriter.create<mlir::tosa::ReduceMaxOp>(op->getLoc(),
                                      out_type, op->getOperands(), attrs);
  // SubOp
  std::vector<Value> operands;
  operands.push_back(op->getOperand(0));
  operands.push_back(reducemax->getResult(0));
  auto sub = rewriter.create<mlir::tosa::SubOp>(op->getLoc(), newType, operands);
  // ExpOp
  auto sub_ty = sub->getResult(0).getType();
  auto exp = rewriter.create<mlir::tosa::ExpOp>(op->getLoc(), sub_ty, sub->getResults());
  // ReduceSumOp ( out_type & attrs same as ReduceMaxOp)
  auto reducesum = rewriter.create<mlir::tosa::ReduceSumOp>(op->getLoc(),
                                      out_type, exp->getResults(), attrs);
  // LogSoftmax ? Softmax ?
  if (log_attr_val){
    // LogOp
    auto reducesum_ty = reducesum->getResult(0).getType();
    auto log = rewriter.create<mlir::tosa::LogOp>(op->getLoc(), reducesum_ty, reducesum->getResults());
    // SubOp
    operands.clear();
    operands.push_back(sub->getResult(0));
    operands.push_back(log->getResult(0));
    auto sub2 = rewriter.create<mlir::tosa::SubOp>(op->getLoc(), newType, operands);
    rewriter.replaceOp(op, sub->getResults());
  } else {
    // ReciprocalOp
    auto reducesum_ty = reducesum->getResult(0).getType();
    auto reciprocal = rewriter.create<mlir::tosa::ReciprocalOp>(
             op->getLoc(), reducesum_ty, reducesum->getResults());
    // MulOp
    auto mul = rewriter.create<mlir::tosa::MulOp>(op->getLoc(), newType,
            exp->getResult(0), reciprocal->getResult(0), rewriter.getI32IntegerAttr(0));
    rewriter.replaceOp(op, mul->getResults());
  }
}

} // namespace tpu_mlir
