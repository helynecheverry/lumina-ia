"""Evaluate a LoRA residual without allocating a merged full-size checkpoint."""
import torch
import torch.nn.functional as functional


def linear_with_lora(module,value,down,up,scale):
    x=value.float()
    base=functional.linear(x,module.weight.float(),module.bias.float() if module.bias is not None else None)
    low=down.to(device=value.device,dtype=torch.float32)
    high=up.to(device=value.device,dtype=torch.float32)
    residual=functional.linear(functional.linear(x,low),high)
    return (base+residual*scale).to(value.dtype)
