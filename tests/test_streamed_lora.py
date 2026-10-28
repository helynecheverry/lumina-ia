import unittest
import torch
from app.streamed_lora import linear_with_lora


class StreamedLoraTest(unittest.TestCase):
    def test_streaming_matches_an_independently_merged_matrix(self):
        torch.manual_seed(77)
        layer=torch.nn.Linear(7,5)
        original=layer.weight.detach().clone()
        down=torch.randn(3,7)
        up=torch.randn(5,3)
        values=torch.randn(2,4,7)
        scale=.5
        expected=values @ (layer.weight+scale*(up@down)).T+layer.bias
        actual=linear_with_lora(layer,values,down,up,scale)
        torch.testing.assert_close(actual,expected,atol=1e-5,rtol=1e-5)
        torch.testing.assert_close(layer.weight,original)
