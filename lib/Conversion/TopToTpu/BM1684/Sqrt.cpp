//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// TPU-MLIR is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//

#include "tpu_mlir/Conversion/TopToTpu/LoweringBM1684.h"

namespace tpu_mlir {
namespace bm1684 {

void SqrtLowering::LoweringF32(PatternRewriter &rewriter,
                               top::SqrtOp op) const {
  auto op_ = op.getOperation();
  op_->setAttr(
      "mode", tpu::ActiveModeAttr::get(op.getContext(), tpu::ActiveMode::SQRT));
  lowering_common_f32<tpu::ActiveOp>(rewriter, op_);
}

void SqrtLowering::LoweringINT8(PatternRewriter &rewriter, top::SqrtOp op,
                                bool asymmetric) const {
  auto stype = module::getStorageType(op.getOutput());
  auto table = create_lookup_table(
      op.getInput(), op.getOutput(), asymmetric,
      [](double val) { return std::sqrt(val); }, 32);
  auto newType = getQuantInt8Type(op.getOutput(), asymmetric);
  rewriter.replaceOpWithNewOp<tpu::LutOp>(op, newType,
                                          ValueRange{op.getInput(), table});
}

} // namespace bm1684
} // namespace tpu_mlir
