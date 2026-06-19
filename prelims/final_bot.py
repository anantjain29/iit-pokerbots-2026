import eval7
import random
from pkbot.actions import ActionFold, ActionCall, ActionCheck, ActionRaise, ActionBid
from pkbot.states import GameInfo, PokerState
from pkbot.base import BaseBot
from pkbot.runner import parse_args, run_bot

# Precomputed starting-hand equity by exact rank and suit combination.
_EQ = {
    '2c2d': 0.5028,
    '2c2h': 0.5031,
    '2c2s': 0.5034,
    '2c3c': 0.3596,
    '2c3d': 0.3226,
    '2c3h': 0.3231,
    '2c3s': 0.3228,
    '2c4c': 0.3685,
    '2c4d': 0.3322,
    '2c4h': 0.332,
    '2c4s': 0.3326,
    '2c5c': 0.3785,
    '2c5d': 0.3428,
    '2c5h': 0.3425,
    '2c5s': 0.3422,
    '2c6c': 0.3765,
    '2c6d': 0.3409,
    '2c6h': 0.3417,
    '2c6s': 0.3405,
    '2c7c': 0.3817,
    '2c7d': 0.3459,
    '2c7h': 0.345,
    '2c7s': 0.3451,
    '2c8c': 0.402,
    '2c8d': 0.3684,
    '2c8h': 0.3683,
    '2c8s': 0.3678,
    '2c9c': 0.4245,
    '2c9d': 0.3916,
    '2c9h': 0.3904,
    '2c9s': 0.3913,
    '2cAc': 0.5734,
    '2cAd': 0.5498,
    '2cAh': 0.5481,
    '2cAs': 0.5485,
    '2cJc': 0.474,
    '2cJd': 0.4431,
    '2cJh': 0.4436,
    '2cJs': 0.4434,
    '2cKc': 0.5326,
    '2cKd': 0.5053,
    '2cKh': 0.505,
    '2cKs': 0.5054,
    '2cQc': 0.5021,
    '2cQd': 0.473,
    '2cQh': 0.4729,
    '2cQs': 0.4729,
    '2cTc': 0.4477,
    '2cTd': 0.4165,
    '2cTh': 0.4164,
    '2cTs': 0.4166,
    '2d2h': 0.5034,
    '2d2s': 0.5028,
    '2d3c': 0.3236,
    '2d3d': 0.3593,
    '2d3h': 0.322,
    '2d3s': 0.3234,
    '2d4c': 0.3322,
    '2d4d': 0.3675,
    '2d4h': 0.3317,
    '2d4s': 0.3323,
    '2d5c': 0.3429,
    '2d5d': 0.3781,
    '2d5h': 0.3428,
    '2d5s': 0.3423,
    '2d6c': 0.3403,
    '2d6d': 0.3763,
    '2d6h': 0.3408,
    '2d6s': 0.3408,
    '2d7c': 0.346,
    '2d7d': 0.382,
    '2d7h': 0.3457,
    '2d7s': 0.346,
    '2d8c': 0.3682,
    '2d8d': 0.4019,
    '2d8h': 0.3686,
    '2d8s': 0.368,
    '2d9c': 0.3907,
    '2d9d': 0.4239,
    '2d9h': 0.3912,
    '2d9s': 0.3916,
    '2dAc': 0.5492,
    '2dAd': 0.5745,
    '2dAh': 0.5496,
    '2dAs': 0.5502,
    '2dJc': 0.4433,
    '2dJd': 0.4738,
    '2dJh': 0.4437,
    '2dJs': 0.4437,
    '2dKc': 0.5053,
    '2dKd': 0.532,
    '2dKh': 0.5045,
    '2dKs': 0.5059,
    '2dQc': 0.4737,
    '2dQd': 0.5021,
    '2dQh': 0.473,
    '2dQs': 0.4721,
    '2dTc': 0.4164,
    '2dTd': 0.447,
    '2dTh': 0.4168,
    '2dTs': 0.4165,
    '2h2s': 0.5031,
    '2h3c': 0.3235,
    '2h3d': 0.3233,
    '2h3h': 0.3604,
    '2h3s': 0.3235,
    '2h4c': 0.3319,
    '2h4d': 0.3317,
    '2h4h': 0.3685,
    '2h4s': 0.3316,
    '2h5c': 0.343,
    '2h5d': 0.3435,
    '2h5h': 0.3783,
    '2h5s': 0.3427,
    '2h6c': 0.3407,
    '2h6d': 0.3418,
    '2h6h': 0.3768,
    '2h6s': 0.3414,
    '2h7c': 0.3465,
    '2h7d': 0.346,
    '2h7h': 0.3807,
    '2h7s': 0.3466,
    '2h8c': 0.3684,
    '2h8d': 0.3682,
    '2h8h': 0.4025,
    '2h8s': 0.3687,
    '2h9c': 0.3915,
    '2h9d': 0.3917,
    '2h9h': 0.4242,
    '2h9s': 0.3914,
    '2hAc': 0.549,
    '2hAd': 0.5484,
    '2hAh': 0.5735,
    '2hAs': 0.5492,
    '2hJc': 0.4446,
    '2hJd': 0.4433,
    '2hJh': 0.4739,
    '2hJs': 0.443,
    '2hKc': 0.5048,
    '2hKd': 0.5045,
    '2hKh': 0.5323,
    '2hKs': 0.5049,
    '2hQc': 0.4724,
    '2hQd': 0.4729,
    '2hQh': 0.5015,
    '2hQs': 0.4733,
    '2hTc': 0.4164,
    '2hTd': 0.4172,
    '2hTh': 0.449,
    '2hTs': 0.4169,
    '2s3c': 0.3224,
    '2s3d': 0.3228,
    '2s3h': 0.3223,
    '2s3s': 0.3597,
    '2s4c': 0.3311,
    '2s4d': 0.3311,
    '2s4h': 0.3313,
    '2s4s': 0.3677,
    '2s5c': 0.3431,
    '2s5d': 0.3429,
    '2s5h': 0.3431,
    '2s5s': 0.3777,
    '2s6c': 0.3421,
    '2s6d': 0.341,
    '2s6h': 0.3413,
    '2s6s': 0.3769,
    '2s7c': 0.3443,
    '2s7d': 0.3461,
    '2s7h': 0.3462,
    '2s7s': 0.3818,
    '2s8c': 0.3687,
    '2s8d': 0.3684,
    '2s8h': 0.3688,
    '2s8s': 0.4034,
    '2s9c': 0.3914,
    '2s9d': 0.3902,
    '2s9h': 0.3914,
    '2s9s': 0.4235,
    '2sAc': 0.549,
    '2sAd': 0.5488,
    '2sAh': 0.5497,
    '2sAs': 0.5734,
    '2sJc': 0.4435,
    '2sJd': 0.4433,
    '2sJh': 0.4429,
    '2sJs': 0.4736,
    '2sKc': 0.5055,
    '2sKd': 0.5052,
    '2sKh': 0.5049,
    '2sKs': 0.5322,
    '2sQc': 0.473,
    '2sQd': 0.473,
    '2sQh': 0.4724,
    '2sQs': 0.5019,
    '2sTc': 0.4163,
    '2sTd': 0.4167,
    '2sTh': 0.4166,
    '2sTs': 0.4492,
    '3c3d': 0.5379,
    '3c3h': 0.5372,
    '3c3s': 0.5381,
    '3c4c': 0.3869,
    '3c4d': 0.3516,
    '3c4h': 0.3518,
    '3c4s': 0.3513,
    '3c5c': 0.3964,
    '3c5d': 0.3625,
    '3c5h': 0.3627,
    '3c5s': 0.363,
    '3c6c': 0.3952,
    '3c6d': 0.3606,
    '3c6h': 0.3604,
    '3c6s': 0.3612,
    '3c7c': 0.4003,
    '3c7d': 0.3663,
    '3c7h': 0.3664,
    '3c7s': 0.3663,
    '3c8c': 0.4084,
    '3c8d': 0.3743,
    '3c8h': 0.3754,
    '3c8s': 0.3748,
    '3c9c': 0.4331,
    '3c9d': 0.4007,
    '3c9h': 0.3989,
    '3c9s': 0.4005,
    '3cAc': 0.5818,
    '3cAd': 0.5582,
    '3cAh': 0.5589,
    '3cAs': 0.5591,
    '3cJc': 0.4819,
    '3cJd': 0.4529,
    '3cJh': 0.452,
    '3cJs': 0.4527,
    '3cKc': 0.5408,
    '3cKd': 0.5146,
    '3cKh': 0.5141,
    '3cKs': 0.5148,
    '3cQc': 0.5098,
    '3cQd': 0.4827,
    '3cQh': 0.4819,
    '3cQs': 0.4826,
    '3cTc': 0.4561,
    '3cTd': 0.4262,
    '3cTh': 0.425,
    '3cTs': 0.4261,
    '3d3h': 0.5367,
    '3d3s': 0.5376,
    '3d4c': 0.3519,
    '3d4d': 0.3864,
    '3d4h': 0.3515,
    '3d4s': 0.3512,
    '3d5c': 0.3628,
    '3d5d': 0.397,
    '3d5h': 0.3628,
    '3d5s': 0.3625,
    '3d6c': 0.3611,
    '3d6d': 0.396,
    '3d6h': 0.3605,
    '3d6s': 0.3607,
    '3d7c': 0.3651,
    '3d7d': 0.4007,
    '3d7h': 0.3659,
    '3d7s': 0.366,
    '3d8c': 0.3748,
    '3d8d': 0.4086,
    '3d8h': 0.3754,
    '3d8s': 0.3744,
    '3d9c': 0.3994,
    '3d9d': 0.4333,
    '3d9h': 0.4006,
    '3d9s': 0.3998,
    '3dAc': 0.5589,
    '3dAd': 0.5829,
    '3dAh': 0.5583,
    '3dAs': 0.5582,
    '3dJc': 0.4528,
    '3dJd': 0.4827,
    '3dJh': 0.4521,
    '3dJs': 0.4513,
    '3dKc': 0.5146,
    '3dKd': 0.5401,
    '3dKh': 0.5138,
    '3dKs': 0.514,
    '3dQc': 0.4825,
    '3dQd': 0.5109,
    '3dQh': 0.4819,
    '3dQs': 0.4826,
    '3dTc': 0.4258,
    '3dTd': 0.4567,
    '3dTh': 0.426,
    '3dTs': 0.426,
    '3h3s': 0.537,
    '3h4c': 0.352,
    '3h4d': 0.3518,
    '3h4h': 0.386,
    '3h4s': 0.3515,
    '3h5c': 0.3617,
    '3h5d': 0.3629,
    '3h5h': 0.3978,
    '3h5s': 0.3639,
    '3h6c': 0.3605,
    '3h6d': 0.3616,
    '3h6h': 0.395,
    '3h6s': 0.361,
    '3h7c': 0.3659,
    '3h7d': 0.3661,
    '3h7h': 0.4003,
    '3h7s': 0.3659,
    '3h8c': 0.3737,
    '3h8d': 0.3746,
    '3h8h': 0.4086,
    '3h8s': 0.3749,
    '3h9c': 0.3993,
    '3h9d': 0.4002,
    '3h9h': 0.4321,
    '3h9s': 0.4001,
    '3hAc': 0.5572,
    '3hAd': 0.5588,
    '3hAh': 0.5827,
    '3hAs': 0.5588,
    '3hJc': 0.4526,
    '3hJd': 0.4527,
    '3hJh': 0.4828,
    '3hJs': 0.4538,
    '3hKc': 0.5138,
    '3hKd': 0.5144,
    '3hKh': 0.5412,
    '3hKs': 0.5146,
    '3hQc': 0.4817,
    '3hQd': 0.4817,
    '3hQh': 0.5106,
    '3hQs': 0.4816,
    '3hTc': 0.4256,
    '3hTd': 0.4264,
    '3hTh': 0.4568,
    '3hTs': 0.4259,
    '3s4c': 0.3515,
    '3s4d': 0.3519,
    '3s4h': 0.3513,
    '3s4s': 0.3867,
    '3s5c': 0.3625,
    '3s5d': 0.3635,
    '3s5h': 0.3627,
    '3s5s': 0.3962,
    '3s6c': 0.3602,
    '3s6d': 0.3611,
    '3s6h': 0.3612,
    '3s6s': 0.3955,
    '3s7c': 0.3664,
    '3s7d': 0.3663,
    '3s7h': 0.3658,
    '3s7s': 0.4006,
    '3s8c': 0.3744,
    '3s8d': 0.3745,
    '3s8h': 0.3752,
    '3s8s': 0.4088,
    '3s9c': 0.4,
    '3s9d': 0.3996,
    '3s9h': 0.3999,
    '3s9s': 0.4323,
    '3sAc': 0.5584,
    '3sAd': 0.5583,
    '3sAh': 0.5592,
    '3sAs': 0.5819,
    '3sJc': 0.4524,
    '3sJd': 0.4531,
    '3sJh': 0.4532,
    '3sJs': 0.4814,
    '3sKc': 0.5147,
    '3sKd': 0.5143,
    '3sKh': 0.5143,
    '3sKs': 0.5401,
    '3sQc': 0.4822,
    '3sQd': 0.4826,
    '3sQh': 0.4816,
    '3sQs': 0.5096,
    '3sTc': 0.4267,
    '3sTd': 0.4246,
    '3sTh': 0.4257,
    '3sTs': 0.4575,
    '4c4d': 0.5703,
    '4c4h': 0.5701,
    '4c4s': 0.5704,
    '4c5c': 0.4151,
    '4c5d': 0.3818,
    '4c5h': 0.3819,
    '4c5s': 0.3817,
    '4c6c': 0.4136,
    '4c6d': 0.3796,
    '4c6h': 0.3798,
    '4c6s': 0.38,
    '4c7c': 0.4179,
    '4c7d': 0.3854,
    '4c7h': 0.3854,
    '4c7s': 0.3853,
    '4c8c': 0.4267,
    '4c8d': 0.3938,
    '4c8h': 0.3947,
    '4c8s': 0.3941,
    '4c9c': 0.4381,
    '4c9d': 0.4063,
    '4c9h': 0.4065,
    '4c9s': 0.4074,
    '4cAc': 0.5907,
    '4cAd': 0.5682,
    '4cAh': 0.5664,
    '4cAs': 0.5678,
    '4cJc': 0.4915,
    '4cJd': 0.4615,
    '4cJh': 0.4619,
    '4cJs': 0.4614,
    '4cKc': 0.5488,
    '4cKd': 0.5237,
    '4cKh': 0.523,
    '4cKs': 0.5235,
    '4cQc': 0.5182,
    '4cQd': 0.4912,
    '4cQh': 0.4912,
    '4cQs': 0.4911,
    '4cTc': 0.4651,
    '4cTd': 0.4345,
    '4cTh': 0.4352,
    '4cTs': 0.4355,
    '4d4h': 0.5702,
    '4d4s': 0.5699,
    '4d5c': 0.3814,
    '4d5d': 0.4151,
    '4d5h': 0.3813,
    '4d5s': 0.3809,
    '4d6c': 0.3801,
    '4d6d': 0.4138,
    '4d6h': 0.3796,
    '4d6s': 0.3801,
    '4d7c': 0.3859,
    '4d7d': 0.4183,
    '4d7h': 0.3856,
    '4d7s': 0.385,
    '4d8c': 0.3941,
    '4d8d': 0.4275,
    '4d8h': 0.3944,
    '4d8s': 0.3952,
    '4d9c': 0.4064,
    '4d9d': 0.4395,
    '4d9h': 0.4069,
    '4d9s': 0.4063,
    '4dAc': 0.5672,
    '4dAd': 0.5901,
    '4dAh': 0.5678,
    '4dAs': 0.5663,
    '4dJc': 0.4617,
    '4dJd': 0.491,
    '4dJh': 0.4615,
    '4dJs': 0.462,
    '4dKc': 0.5236,
    '4dKd': 0.5491,
    '4dKh': 0.5232,
    '4dKs': 0.5229,
    '4dQc': 0.491,
    '4dQd': 0.5184,
    '4dQh': 0.4909,
    '4dQs': 0.4921,
    '4dTc': 0.435,
    '4dTd': 0.4649,
    '4dTh': 0.4356,
    '4dTs': 0.4346,
    '4h4s': 0.5707,
    '4h5c': 0.3811,
    '4h5d': 0.3813,
    '4h5h': 0.4142,
    '4h5s': 0.3811,
    '4h6c': 0.3795,
    '4h6d': 0.3795,
    '4h6h': 0.4145,
    '4h6s': 0.3802,
    '4h7c': 0.3852,
    '4h7d': 0.3859,
    '4h7h': 0.4184,
    '4h7s': 0.3859,
    '4h8c': 0.3945,
    '4h8d': 0.3946,
    '4h8h': 0.4269,
    '4h8s': 0.3953,
    '4h9c': 0.4075,
    '4h9d': 0.407,
    '4h9h': 0.4381,
    '4h9s': 0.4072,
    '4hAc': 0.5675,
    '4hAd': 0.566,
    '4hAh': 0.5913,
    '4hAs': 0.5673,
    '4hJc': 0.461,
    '4hJd': 0.4627,
    '4hJh': 0.4907,
    '4hJs': 0.4623,
    '4hKc': 0.5243,
    '4hKd': 0.5238,
    '4hKh': 0.5482,
    '4hKs': 0.5227,
    '4hQc': 0.4917,
    '4hQd': 0.4901,
    '4hQh': 0.5185,
    '4hQs': 0.4915,
    '4hTc': 0.4351,
    '4hTd': 0.4356,
    '4hTh': 0.4663,
    '4hTs': 0.4338,
    '4s5c': 0.3822,
    '4s5d': 0.3818,
    '4s5h': 0.382,
    '4s5s': 0.4143,
    '4s6c': 0.3796,
    '4s6d': 0.3805,
    '4s6h': 0.3803,
    '4s6s': 0.413,
    '4s7c': 0.3847,
    '4s7d': 0.3858,
    '4s7h': 0.3852,
    '4s7s': 0.4191,
    '4s8c': 0.394,
    '4s8d': 0.3947,
    '4s8h': 0.3947,
    '4s8s': 0.4269,
    '4s9c': 0.4068,
    '4s9d': 0.4065,
    '4s9h': 0.4072,
    '4s9s': 0.439,
    '4sAc': 0.5674,
    '4sAd': 0.5676,
    '4sAh': 0.5671,
    '4sAs': 0.5903,
    '4sJc': 0.4618,
    '4sJd': 0.4618,
    '4sJh': 0.462,
    '4sJs': 0.491,
    '4sKc': 0.5234,
    '4sKd': 0.524,
    '4sKh': 0.5231,
    '4sKs': 0.549,
    '4sQc': 0.4914,
    '4sQd': 0.4914,
    '4sQh': 0.4908,
    '4sQs': 0.5176,
    '4sTc': 0.4346,
    '4sTd': 0.4349,
    '4sTh': 0.4342,
    '4sTs': 0.4657,
    '5c5d': 0.6034,
    '5c5h': 0.6031,
    '5c5s': 0.6038,
    '5c6c': 0.4323,
    '5c6d': 0.4,
    '5c6h': 0.3992,
    '5c6s': 0.3994,
    '5c7c': 0.4363,
    '5c7d': 0.405,
    '5c7h': 0.4054,
    '5c7s': 0.4057,
    '5c8c': 0.4458,
    '5c8d': 0.4144,
    '5c8h': 0.415,
    '5c8s': 0.4146,
    '5c9c': 0.4576,
    '5c9d': 0.4263,
    '5c9h': 0.4267,
    '5c9s': 0.4268,
    '5cAc': 0.5982,
    '5cAd': 0.5763,
    '5cAh': 0.5768,
    '5cAs': 0.5774,
    '5cJc': 0.5,
    '5cJd': 0.4716,
    '5cJh': 0.4717,
    '5cJs': 0.4717,
    '5cKc': 0.5576,
    '5cKd': 0.5338,
    '5cKh': 0.5333,
    '5cKs': 0.5328,
    '5cQc': 0.5281,
    '5cQd': 0.5013,
    '5cQh': 0.5018,
    '5cQs': 0.5019,
    '5cTc': 0.4719,
    '5cTd': 0.4419,
    '5cTh': 0.4426,
    '5cTs': 0.4427,
    '5d5h': 0.6031,
    '5d5s': 0.6031,
    '5d6c': 0.3999,
    '5d6d': 0.4319,
    '5d6h': 0.3994,
    '5d6s': 0.3994,
    '5d7c': 0.4051,
    '5d7d': 0.4371,
    '5d7h': 0.4043,
    '5d7s': 0.4059,
    '5d8c': 0.4148,
    '5d8d': 0.4456,
    '5d8h': 0.4141,
    '5d8s': 0.4136,
    '5d9c': 0.4269,
    '5d9d': 0.4578,
    '5d9h': 0.4262,
    '5d9s': 0.4269,
    '5dAc': 0.5761,
    '5dAd': 0.5994,
    '5dAh': 0.5772,
    '5dAs': 0.5767,
    '5dJc': 0.4724,
    '5dJd': 0.4999,
    '5dJh': 0.4718,
    '5dJs': 0.4719,
    '5dKc': 0.5326,
    '5dKd': 0.5581,
    '5dKh': 0.5328,
    '5dKs': 0.5325,
    '5dQc': 0.5008,
    '5dQd': 0.5278,
    '5dQh': 0.5022,
    '5dQs': 0.5007,
    '5dTc': 0.4426,
    '5dTd': 0.4724,
    '5dTh': 0.443,
    '5dTs': 0.4431,
    '5h5s': 0.6035,
    '5h6c': 0.3992,
    '5h6d': 0.4001,
    '5h6h': 0.4317,
    '5h6s': 0.3999,
    '5h7c': 0.4052,
    '5h7d': 0.4051,
    '5h7h': 0.4371,
    '5h7s': 0.4055,
    '5h8c': 0.4144,
    '5h8d': 0.4142,
    '5h8h': 0.4454,
    '5h8s': 0.4143,
    '5h9c': 0.4269,
    '5h9d': 0.4274,
    '5h9h': 0.4568,
    '5h9s': 0.4269,
    '5hAc': 0.576,
    '5hAd': 0.5776,
    '5hAh': 0.5998,
    '5hAs': 0.5765,
    '5hJc': 0.4722,
    '5hJd': 0.4713,
    '5hJh': 0.4997,
    '5hJs': 0.4707,
    '5hKc': 0.5334,
    '5hKd': 0.5323,
    '5hKh': 0.5573,
    '5hKs': 0.5336,
    '5hQc': 0.5019,
    '5hQd': 0.5007,
    '5hQh': 0.5271,
    '5hQs': 0.5013,
    '5hTc': 0.442,
    '5hTd': 0.443,
    '5hTh': 0.4732,
    '5hTs': 0.4424,
    '5s6c': 0.3992,
    '5s6d': 0.3992,
    '5s6h': 0.3994,
    '5s6s': 0.4316,
    '5s7c': 0.404,
    '5s7d': 0.4053,
    '5s7h': 0.4051,
    '5s7s': 0.4363,
    '5s8c': 0.4148,
    '5s8d': 0.4142,
    '5s8h': 0.4151,
    '5s8s': 0.4459,
    '5s9c': 0.4273,
    '5s9d': 0.4263,
    '5s9h': 0.4267,
    '5s9s': 0.4569,
    '5sAc': 0.5767,
    '5sAd': 0.5775,
    '5sAh': 0.578,
    '5sAs': 0.5988,
    '5sJc': 0.4714,
    '5sJd': 0.4713,
    '5sJh': 0.4708,
    '5sJs': 0.5004,
    '5sKc': 0.5333,
    '5sKd': 0.5326,
    '5sKh': 0.5332,
    '5sKs': 0.5579,
    '5sQc': 0.5005,
    '5sQd': 0.501,
    '5sQh': 0.5011,
    '5sQs': 0.5277,
    '5sTc': 0.4427,
    '5sTd': 0.4419,
    '5sTh': 0.4428,
    '5sTs': 0.4725,
    '6c6d': 0.6327,
    '6c6h': 0.6326,
    '6c6s': 0.6323,
    '6c7c': 0.4537,
    '6c7d': 0.4238,
    '6c7h': 0.4228,
    '6c7s': 0.4234,
    '6c8c': 0.4628,
    '6c8d': 0.4321,
    '6c8h': 0.4321,
    '6c8s': 0.4334,
    '6c9c': 0.4743,
    '6c9d': 0.4452,
    '6c9h': 0.4458,
    '6c9s': 0.4451,
    '6cAc': 0.5991,
    '6cAd': 0.5779,
    '6cAh': 0.5763,
    '6cAs': 0.5773,
    '6cJc': 0.5063,
    '6cJd': 0.478,
    '6cJh': 0.4787,
    '6cJs': 0.479,
    '6cKc': 0.5664,
    '6cKd': 0.5415,
    '6cKh': 0.5423,
    '6cKs': 0.5421,
    '6cQc': 0.5359,
    '6cQd': 0.5105,
    '6cQh': 0.5096,
    '6cQs': 0.5101,
    '6cTc': 0.4895,
    '6cTd': 0.4608,
    '6cTh': 0.4618,
    '6cTs': 0.4612,
    '6d6h': 0.6328,
    '6d6s': 0.6335,
    '6d7c': 0.4226,
    '6d7d': 0.4536,
    '6d7h': 0.4225,
    '6d7s': 0.4243,
    '6d8c': 0.4328,
    '6d8d': 0.4628,
    '6d8h': 0.4324,
    '6d8s': 0.4324,
    '6d9c': 0.4456,
    '6d9d': 0.4745,
    '6d9h': 0.4452,
    '6d9s': 0.4441,
    '6dAc': 0.5764,
    '6dAd': 0.5991,
    '6dAh': 0.5774,
    '6dAs': 0.5766,
    '6dJc': 0.4777,
    '6dJd': 0.5059,
    '6dJh': 0.4787,
    '6dJs': 0.4781,
    '6dKc': 0.5425,
    '6dKd': 0.5668,
    '6dKh': 0.5422,
    '6dKs': 0.5422,
    '6dQc': 0.5103,
    '6dQd': 0.536,
    '6dQh': 0.5103,
    '6dQs': 0.5103,
    '6dTc': 0.4604,
    '6dTd': 0.49,
    '6dTh': 0.4611,
    '6dTs': 0.461,
    '6h6s': 0.633,
    '6h7c': 0.4224,
    '6h7d': 0.4232,
    '6h7h': 0.4537,
    '6h7s': 0.4238,
    '6h8c': 0.4326,
    '6h8d': 0.4325,
    '6h8h': 0.4628,
    '6h8s': 0.4328,
    '6h9c': 0.4453,
    '6h9d': 0.4455,
    '6h9h': 0.4738,
    '6h9s': 0.4443,
    '6hAc': 0.5768,
    '6hAd': 0.5769,
    '6hAh': 0.599,
    '6hAs': 0.5765,
    '6hJc': 0.4788,
    '6hJd': 0.4782,
    '6hJh': 0.5062,
    '6hJs': 0.4787,
    '6hKc': 0.5418,
    '6hKd': 0.542,
    '6hKh': 0.5671,
    '6hKs': 0.5418,
    '6hQc': 0.5101,
    '6hQd': 0.5103,
    '6hQh': 0.5361,
    '6hQs': 0.5101,
    '6hTc': 0.4611,
    '6hTd': 0.461,
    '6hTh': 0.4896,
    '6hTs': 0.4612,
    '6s7c': 0.4231,
    '6s7d': 0.4232,
    '6s7h': 0.4231,
    '6s7s': 0.4538,
    '6s8c': 0.4314,
    '6s8d': 0.4325,
    '6s8h': 0.432,
    '6s8s': 0.4626,
    '6s9c': 0.4446,
    '6s9d': 0.4448,
    '6s9h': 0.4449,
    '6s9s': 0.4736,
    '6sAc': 0.577,
    '6sAd': 0.5761,
    '6sAh': 0.577,
    '6sAs': 0.5993,
    '6sJc': 0.4789,
    '6sJd': 0.4788,
    '6sJh': 0.4774,
    '6sJs': 0.5066,
    '6sKc': 0.5425,
    '6sKd': 0.5426,
    '6sKh': 0.5423,
    '6sKs': 0.5656,
    '6sQc': 0.5103,
    '6sQd': 0.5109,
    '6sQh': 0.5104,
    '6sQs': 0.5364,
    '6sTc': 0.4617,
    '6sTd': 0.4602,
    '6sTh': 0.4606,
    '6sTs': 0.4893,
    '7c7d': 0.662,
    '7c7h': 0.6623,
    '7c7s': 0.6616,
    '7c8c': 0.4793,
    '7c8d': 0.4509,
    '7c8h': 0.4504,
    '7c8s': 0.4501,
    '7c9c': 0.4909,
    '7c9d': 0.4635,
    '7c9h': 0.4618,
    '7c9s': 0.4623,
    '7cAc': 0.6098,
    '7cAd': 0.5885,
    '7cAh': 0.5884,
    '7cAs': 0.588,
    '7cJc': 0.523,
    '7cJd': 0.4972,
    '7cJh': 0.4972,
    '7cJs': 0.496,
    '7cKc': 0.5753,
    '7cKd': 0.5519,
    '7cKh': 0.5517,
    '7cKs': 0.5516,
    '7cQc': 0.5428,
    '7cQd': 0.5176,
    '7cQh': 0.5174,
    '7cQs': 0.5169,
    '7cTc': 0.5059,
    '7cTd': 0.4789,
    '7cTh': 0.4787,
    '7cTs': 0.4783,
    '7d7h': 0.6619,
    '7d7s': 0.6622,
    '7d8c': 0.4503,
    '7d8d': 0.4802,
    '7d8h': 0.4509,
    '7d8s': 0.4502,
    '7d9c': 0.4624,
    '7d9d': 0.4908,
    '7d9h': 0.4629,
    '7d9s': 0.4623,
    '7dAc': 0.5882,
    '7dAd': 0.6097,
    '7dAh': 0.588,
    '7dAs': 0.5884,
    '7dJc': 0.497,
    '7dJd': 0.5222,
    '7dJh': 0.4957,
    '7dJs': 0.4964,
    '7dKc': 0.5534,
    '7dKd': 0.5762,
    '7dKh': 0.5525,
    '7dKs': 0.5521,
    '7dQc': 0.5177,
    '7dQd': 0.5438,
    '7dQh': 0.5176,
    '7dQs': 0.5179,
    '7dTc': 0.4787,
    '7dTd': 0.5066,
    '7dTh': 0.479,
    '7dTs': 0.4783,
    '7h7s': 0.6632,
    '7h8c': 0.4499,
    '7h8d': 0.451,
    '7h8h': 0.4786,
    '7h8s': 0.4506,
    '7h9c': 0.4633,
    '7h9d': 0.4626,
    '7h9h': 0.4909,
    '7h9s': 0.463,
    '7hAc': 0.5882,
    '7hAd': 0.5887,
    '7hAh': 0.6096,
    '7hAs': 0.5889,
    '7hJc': 0.4969,
    '7hJd': 0.4965,
    '7hJh': 0.5232,
    '7hJs': 0.4961,
    '7hKc': 0.5523,
    '7hKd': 0.5516,
    '7hKh': 0.5763,
    '7hKs': 0.5526,
    '7hQc': 0.518,
    '7hQd': 0.5176,
    '7hQh': 0.5431,
    '7hQs': 0.5177,
    '7hTc': 0.478,
    '7hTd': 0.4792,
    '7hTh': 0.506,
    '7hTs': 0.4794,
    '7s8c': 0.4501,
    '7s8d': 0.4504,
    '7s8h': 0.4508,
    '7s8s': 0.4795,
    '7s9c': 0.4631,
    '7s9d': 0.4636,
    '7s9h': 0.4629,
    '7s9s': 0.4907,
    '7sAc': 0.5883,
    '7sAd': 0.5883,
    '7sAh': 0.5878,
    '7sAs': 0.6088,
    '7sJc': 0.4975,
    '7sJd': 0.4975,
    '7sJh': 0.4977,
    '7sJs': 0.5239,
    '7sKc': 0.5526,
    '7sKd': 0.5525,
    '7sKh': 0.5518,
    '7sKs': 0.5758,
    '7sQc': 0.517,
    '7sQd': 0.5172,
    '7sQh': 0.5181,
    '7sQs': 0.5435,
    '7sTc': 0.4795,
    '7sTd': 0.4787,
    '7sTh': 0.478,
    '7sTs': 0.5064,
    '8c8d': 0.6917,
    '8c8h': 0.6917,
    '8c8s': 0.6916,
    '8c9c': 0.5066,
    '8c9d': 0.4813,
    '8c9h': 0.4811,
    '8c9s': 0.4812,
    '8cAc': 0.6197,
    '8cAd': 0.5982,
    '8cAh': 0.5983,
    '8cAs': 0.5988,
    '8cJc': 0.5403,
    '8cJd': 0.5147,
    '8cJh': 0.5152,
    '8cJs': 0.5142,
    '8cKc': 0.5829,
    '8cKd': 0.56,
    '8cKh': 0.5606,
    '8cKs': 0.5595,
    '8cQc': 0.5609,
    '8cQd': 0.5366,
    '8cQh': 0.5353,
    '8cQs': 0.5352,
    '8cTc': 0.5234,
    '8cTd': 0.4969,
    '8cTh': 0.497,
    '8cTs': 0.4968,
    '8d8h': 0.6914,
    '8d8s': 0.6919,
    '8d9c': 0.4818,
    '8d9d': 0.5077,
    '8d9h': 0.4817,
    '8d9s': 0.4807,
    '8dAc': 0.5982,
    '8dAd': 0.6206,
    '8dAh': 0.5981,
    '8dAs': 0.5983,
    '8dJc': 0.5147,
    '8dJd': 0.5397,
    '8dJh': 0.5151,
    '8dJs': 0.5156,
    '8dKc': 0.5598,
    '8dKd': 0.5821,
    '8dKh': 0.5606,
    '8dKs': 0.5614,
    '8dQc': 0.5361,
    '8dQd': 0.5597,
    '8dQh': 0.5354,
    '8dQs': 0.5361,
    '8dTc': 0.4976,
    '8dTd': 0.5229,
    '8dTh': 0.4971,
    '8dTs': 0.4963,
    '8h8s': 0.6917,
    '8h9c': 0.4815,
    '8h9d': 0.4809,
    '8h9h': 0.5085,
    '8h9s': 0.4817,
    '8hAc': 0.5989,
    '8hAd': 0.5977,
    '8hAh': 0.619,
    '8hAs': 0.5981,
    '8hJc': 0.5157,
    '8hJd': 0.5154,
    '8hJh': 0.5401,
    '8hJs': 0.5145,
    '8hKc': 0.5597,
    '8hKd': 0.5606,
    '8hKh': 0.583,
    '8hKs': 0.5605,
    '8hQc': 0.5361,
    '8hQd': 0.5356,
    '8hQh': 0.559,
    '8hQs': 0.5364,
    '8hTc': 0.4965,
    '8hTd': 0.4966,
    '8hTh': 0.5237,
    '8hTs': 0.4974,
    '8s9c': 0.4806,
    '8s9d': 0.4811,
    '8s9h': 0.4803,
    '8s9s': 0.5071,
    '8sAc': 0.5986,
    '8sAd': 0.5981,
    '8sAh': 0.5989,
    '8sAs': 0.6195,
    '8sJc': 0.5144,
    '8sJd': 0.5146,
    '8sJh': 0.5147,
    '8sJs': 0.5395,
    '8sKc': 0.5604,
    '8sKd': 0.5605,
    '8sKh': 0.5606,
    '8sKs': 0.5827,
    '8sQc': 0.536,
    '8sQd': 0.5368,
    '8sQh': 0.5362,
    '8sQs': 0.5607,
    '8sTc': 0.4982,
    '8sTd': 0.4961,
    '8sTh': 0.4967,
    '8sTs': 0.5239,
    '9c9d': 0.72,
    '9c9h': 0.7205,
    '9c9s': 0.7207,
    '9cAc': 0.6275,
    '9cAd': 0.6083,
    '9cAh': 0.6081,
    '9cAs': 0.6079,
    '9cJc': 0.5564,
    '9cJd': 0.5326,
    '9cJh': 0.5324,
    '9cJs': 0.5329,
    '9cKc': 0.5998,
    '9cKd': 0.5784,
    '9cKh': 0.5787,
    '9cKs': 0.578,
    '9cQc': 0.5772,
    '9cQd': 0.5526,
    '9cQh': 0.5534,
    '9cQs': 0.5536,
    '9cTc': 0.5403,
    '9cTd': 0.5144,
    '9cTh': 0.5159,
    '9cTs': 0.5155,
    '9d9h': 0.7213,
    '9d9s': 0.7205,
    '9dAc': 0.608,
    '9dAd': 0.6281,
    '9dAh': 0.607,
    '9dAs': 0.6074,
    '9dJc': 0.5325,
    '9dJd': 0.5567,
    '9dJh': 0.5333,
    '9dJs': 0.5317,
    '9dKc': 0.5775,
    '9dKd': 0.6003,
    '9dKh': 0.578,
    '9dKs': 0.5778,
    '9dQc': 0.5539,
    '9dQd': 0.5772,
    '9dQh': 0.5529,
    '9dQs': 0.5532,
    '9dTc': 0.5158,
    '9dTd': 0.5398,
    '9dTh': 0.5147,
    '9dTs': 0.515,
    '9h9s': 0.7208,
    '9hAc': 0.6071,
    '9hAd': 0.6079,
    '9hAh': 0.6275,
    '9hAs': 0.6082,
    '9hJc': 0.5327,
    '9hJd': 0.5326,
    '9hJh': 0.5569,
    '9hJs': 0.5328,
    '9hKc': 0.5789,
    '9hKd': 0.5781,
    '9hKh': 0.6004,
    '9hKs': 0.5786,
    '9hQc': 0.5536,
    '9hQd': 0.5541,
    '9hQh': 0.5767,
    '9hQs': 0.5531,
    '9hTc': 0.5159,
    '9hTd': 0.5147,
    '9hTh': 0.5409,
    '9hTs': 0.5147,
    '9sAc': 0.607,
    '9sAd': 0.6088,
    '9sAh': 0.6072,
    '9sAs': 0.6282,
    '9sJc': 0.5318,
    '9sJd': 0.5321,
    '9sJh': 0.5316,
    '9sJs': 0.5565,
    '9sKc': 0.578,
    '9sKd': 0.578,
    '9sKh': 0.5783,
    '9sKs': 0.6001,
    '9sQc': 0.5528,
    '9sQd': 0.5538,
    '9sQh': 0.5538,
    '9sQs': 0.5762,
    '9sTc': 0.5141,
    '9sTd': 0.5149,
    '9sTh': 0.5158,
    '9sTs': 0.5408,
    'AcAd': 0.8519,
    'AcAh': 0.8519,
    'AcAs': 0.8521,
    'AdAh': 0.8514,
    'AdAs': 0.8524,
    'AhAs': 0.8519,
    'JcAc': 0.6533,
    'JcAd': 0.6358,
    'JcAh': 0.6353,
    'JcAs': 0.6349,
    'JcJd': 0.7747,
    'JcJh': 0.7745,
    'JcJs': 0.7751,
    'JcKc': 0.6258,
    'JcKd': 0.6055,
    'JcKh': 0.6054,
    'JcKs': 0.6054,
    'JcQc': 0.603,
    'JcQd': 0.5811,
    'JcQh': 0.5811,
    'JcQs': 0.5809,
    'JdAc': 0.6361,
    'JdAd': 0.6535,
    'JdAh': 0.6363,
    'JdAs': 0.6355,
    'JdJh': 0.775,
    'JdJs': 0.7745,
    'JdKc': 0.6053,
    'JdKd': 0.6259,
    'JdKh': 0.6057,
    'JdKs': 0.606,
    'JdQc': 0.5806,
    'JdQd': 0.6025,
    'JdQh': 0.5825,
    'JdQs': 0.5811,
    'JhAc': 0.6362,
    'JhAd': 0.6353,
    'JhAh': 0.6543,
    'JhAs': 0.6347,
    'JhJs': 0.7743,
    'JhKc': 0.6047,
    'JhKd': 0.6063,
    'JhKh': 0.6248,
    'JhKs': 0.6053,
    'JhQc': 0.5813,
    'JhQd': 0.5805,
    'JhQh': 0.602,
    'JhQs': 0.5813,
    'JsAc': 0.6353,
    'JsAd': 0.6355,
    'JsAh': 0.6361,
    'JsAs': 0.6547,
    'JsKc': 0.6048,
    'JsKd': 0.6058,
    'JsKh': 0.606,
    'JsKs': 0.6263,
    'JsQc': 0.5813,
    'JsQd': 0.5806,
    'JsQh': 0.5814,
    'JsQs': 0.6038,
    'KcAc': 0.6703,
    'KcAd': 0.6523,
    'KcAh': 0.6534,
    'KcAs': 0.6528,
    'KcKd': 0.8238,
    'KcKh': 0.8238,
    'KcKs': 0.8242,
    'KdAc': 0.6532,
    'KdAd': 0.6701,
    'KdAh': 0.6534,
    'KdAs': 0.6536,
    'KdKh': 0.8243,
    'KdKs': 0.8233,
    'KhAc': 0.6534,
    'KhAd': 0.6533,
    'KhAh': 0.6706,
    'KhAs': 0.6534,
    'KhKs': 0.824,
    'KsAc': 0.6534,
    'KsAd': 0.6526,
    'KsAh': 0.6533,
    'KsAs': 0.6705,
    'QcAc': 0.6624,
    'QcAd': 0.6446,
    'QcAh': 0.6443,
    'QcAs': 0.6452,
    'QcKc': 0.6334,
    'QcKd': 0.614,
    'QcKh': 0.6146,
    'QcKs': 0.6141,
    'QcQd': 0.7988,
    'QcQh': 0.7993,
    'QcQs': 0.7991,
    'QdAc': 0.6447,
    'QdAd': 0.6616,
    'QdAh': 0.6442,
    'QdAs': 0.644,
    'QdKc': 0.6144,
    'QdKd': 0.633,
    'QdKh': 0.6152,
    'QdKs': 0.615,
    'QdQh': 0.7991,
    'QdQs': 0.8,
    'QhAc': 0.6446,
    'QhAd': 0.6434,
    'QhAh': 0.6619,
    'QhAs': 0.6447,
    'QhKc': 0.6143,
    'QhKd': 0.6142,
    'QhKh': 0.6343,
    'QhKs': 0.6143,
    'QhQs': 0.7994,
    'QsAc': 0.6443,
    'QsAd': 0.6443,
    'QsAh': 0.6442,
    'QsAs': 0.6623,
    'QsKc': 0.614,
    'QsKd': 0.6141,
    'QsKh': 0.6155,
    'QsKs': 0.6342,
    'TcAc': 0.6464,
    'TcAd': 0.6271,
    'TcAh': 0.6267,
    'TcAs': 0.6266,
    'TcJc': 0.575,
    'TcJd': 0.5533,
    'TcJh': 0.5515,
    'TcJs': 0.5522,
    'TcKc': 0.6184,
    'TcKd': 0.5978,
    'TcKh': 0.5972,
    'TcKs': 0.5968,
    'TcQc': 0.5947,
    'TcQd': 0.5724,
    'TcQh': 0.5729,
    'TcQs': 0.5726,
    'TcTd': 0.7506,
    'TcTh': 0.7492,
    'TcTs': 0.7495,
    'TdAc': 0.6277,
    'TdAd': 0.647,
    'TdAh': 0.6274,
    'TdAs': 0.6281,
    'TdJc': 0.5516,
    'TdJd': 0.5761,
    'TdJh': 0.5523,
    'TdJs': 0.5538,
    'TdKc': 0.597,
    'TdKd': 0.6182,
    'TdKh': 0.597,
    'TdKs': 0.5974,
    'TdQc': 0.5728,
    'TdQd': 0.5946,
    'TdQh': 0.5731,
    'TdQs': 0.573,
    'TdTh': 0.7494,
    'TdTs': 0.7502,
    'ThAc': 0.6272,
    'ThAd': 0.6274,
    'ThAh': 0.6451,
    'ThAs': 0.6283,
    'ThJc': 0.552,
    'ThJd': 0.5521,
    'ThJh': 0.576,
    'ThJs': 0.5527,
    'ThKc': 0.597,
    'ThKd': 0.5973,
    'ThKh': 0.618,
    'ThKs': 0.5971,
    'ThQc': 0.5732,
    'ThQd': 0.5734,
    'ThQh': 0.5948,
    'ThQs': 0.5726,
    'ThTs': 0.7498,
    'TsAc': 0.6266,
    'TsAd': 0.6266,
    'TsAh': 0.6269,
    'TsAs': 0.6464,
    'TsJc': 0.553,
    'TsJd': 0.5521,
    'TsJh': 0.5531,
    'TsJs': 0.5755,
    'TsKc': 0.597,
    'TsKd': 0.597,
    'TsKh': 0.5971,
    'TsKs': 0.6177,
    'TsQc': 0.5729,
    'TsQd': 0.5726,
    'TsQh': 0.5725,
    'TsQs': 0.5945
}

_RV = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
       'T':10,'J':11,'Q':12,'K':13,'A':14}

# Suit ordering must match the key generation used to build _EQ:
# within equal rank, suits go c < d < h < s
_SUIT_ORD = {'c': 0, 'd': 1, 'h': 2, 's': 3}

# Game constants (from rules)
STACK = 5000
BIG_BLIND = 20
SMALL_BLIND = 10


def _eq_key(c1, c2):
    """
    Return the canonical _EQ lookup key for two hole cards.

    The table was generated with lower-rank card first; within equal rank,
    lower suit (c < d < h < s) comes first.  Sorting by (_RV, _SUIT_ORD)
    reproduces that ordering exactly.
    """
    def sort_key(c):
        return (_RV[c[0]], _SUIT_ORD[c[1]])
    if sort_key(c1) <= sort_key(c2):
        return c1 + c2
    return c2 + c1


class DominatorBot(BaseBot):
    """Adaptive strategy balancing equity, information, and pot odds."""

    def __init__(self):
        self.eq_tbl = _EQ
        self.all_cards = [
            f'{r}{s}' for s in 'cdhs' for r in '23456789TJQKA'
        ]
        self.e7 = {c: eval7.Card(c) for c in self.all_cards}

        # Recalibrate opponent statistics in short windows to adapt quickly.
        self.hands_played = 0
        self.hands_since_recal = 0
        self.rw_raises = 0
        self.rw_folds = 0
        self.rw_calls = 0
        self.cum_raises = 0
        self.cum_folds = 0
        self.cum_calls = 0
        self.cum_total = 0

        # Derived opponent-response thresholds.
        self.call_scale = 1.00
        self.aggro_boost = 0.00
        self.opp_fold_rate = 0.35
        self.opp_aggro_rate = 0.22

        # Per-hand state.
        self.seen_opp_card = None
        self.opp_has_info = False
        self.my_bid = 0
        self.pot_at_auction = 0
        self.auction_done = False
        self.chips_before_auction = None

        # Recent bids drive the opponent-bid estimate.
        self.opp_bid_history = []
        self.opp_bid_avg = 45.0

    def on_hand_start(self, gi: GameInfo, cs: PokerState):
        self.hands_played += 1
        self.hands_since_recal += 1
        self.seen_opp_card = None
        self.opp_has_info = False
        self.my_bid = 0
        self.pot_at_auction = 0
        self.auction_done = False
        self.chips_before_auction = None

    def on_hand_end(self, gi: GameInfo, cs: PokerState):
        self.cum_total += 1
        if cs.payoff > 0 and cs.my_wager > cs.opp_wager:
            self.rw_folds += 1
            self.cum_folds += 1
        if cs.opp_wager > 80:
            self.rw_raises += 1
            self.cum_raises += 1
        elif cs.opp_wager > 20:
            self.rw_calls += 1
            self.cum_calls += 1
        if self.hands_since_recal >= 18:
            self._recalibrate()

    def _recalibrate(self):
        n = max(1, self.hands_since_recal)
        ra = self.rw_raises / n
        rf = self.rw_folds / n
        ca = self.cum_raises / max(1, self.cum_total)
        cf = self.cum_folds / max(1, self.cum_total)
        ba = ra * 0.65 + ca * 0.35
        bf = rf * 0.65 + cf * 0.35
        self.opp_aggro_rate = ba
        self.opp_fold_rate = bf
        if   ba > 0.50: self.call_scale = 0.60
        elif ba > 0.40: self.call_scale = 0.70
        elif ba > 0.30: self.call_scale = 0.82
        elif ba < 0.12: self.call_scale = 1.28
        else:            self.call_scale = 1.00
        self.aggro_boost = min(0.28, max(0.0, bf - 0.10) * 0.60)
        self.hands_since_recal = 0
        self.rw_raises = 0
        self.rw_folds = 0
        self.rw_calls = 0

    def _tex(self, board):
        if not board:
            return {}
        ranks = [c[0] for c in board]
        suits = [c[1] for c in board]
        vals = sorted(_RV[r] for r in ranks)
        sc = [suits.count(s) for s in 'cdhs']
        mx_s = max(sc)
        paired = len(ranks) != len(set(ranks))
        trips = any(ranks.count(r) >= 3 for r in set(ranks))
        monotone = mx_s >= 4
        flush_draw = mx_s >= 3
        connected = any(vals[i+2] - vals[i] <= 4 for i in range(len(vals) - 2)) if len(vals) >= 3 else False
        ace_high = 14 in vals
        return dict(paired=paired, trips=trips, monotone=monotone,
                    flush_draw=flush_draw, connected=connected, ace_high=ace_high)

    def _draws(self, hand, board):
        if len(board) >= 5:
            return {'flush': False, 'oesd': False, 'gutshot': False, 'combo': False}
        all_c = hand + board
        suits = [c[1] for c in all_c]
        # 4 to a suit = flush draw; 5+ = made flush (not a draw)
        flush = any(suits.count(s) == 4 for s in 'cdhs')
        vals = sorted(set(_RV[c[0]] for c in all_c))
        if 14 in vals:
            vals = [1] + vals
        oesd = gutshot = False
        for i in range(len(vals)):
            window = [v for v in vals if vals[i] <= v <= vals[i] + 4]
            cnt = len(window)
            if cnt == 5:
                # 5 cards spanning exactly 4 = made straight, not a draw
                pass
            elif cnt == 4:
                mn, mx = min(window), max(window)
                if mx - mn == 3:
                    oesd = True
                else:
                    gutshot = True
        return {'flush': flush, 'oesd': oesd, 'gutshot': gutshot,
                'combo': flush and (oesd or gutshot)}

    def _classify(self, hand, board):
        if not board:
            return 'preflop'
        mr = [_RV[c[0]] for c in hand]
        br = [_RV[c[0]] for c in board]
        all_c = hand + board

        # --- Made flush detection ---
        suits = [c[1] for c in all_c]
        has_flush = any(suits.count(s) >= 5 for s in 'cdhs')

        # --- Made straight detection ---
        vals = sorted(set(_RV[c[0]] for c in all_c))
        if 14 in vals:
            vals = [1] + vals
        has_straight = False
        for i in range(len(vals) - 4):
            if vals[i + 4] - vals[i] == 4:
                has_straight = True
                break

        # Straight flush / flush / straight are all top-tier made hands
        if has_flush and has_straight:
            return 'straight_flush'
        if has_flush:
            return 'flush'
        if has_straight:
            return 'straight'

        if mr[0] == mr[1] and mr[0] in br:
            return 'set'
        pairs = sum(1 for r in mr if r in br)
        if pairs == 2 and mr[0] != mr[1]:
            return 'two_pair'
        if mr[0] == mr[1] and mr[0] > max(br):
            return 'overpair'
        if pairs >= 1:
            pr = max(r for r in mr if r in br)
            if pr == max(br):
                kick = max(r for r in mr if r != pr) if mr[0] != mr[1] else pr
                return 'tpgk' if kick >= 10 else 'top_pair'
            return 'mid_pair'
        if mr[0] == mr[1]:
            return 'underpair'
        draws = self._draws(hand, board)
        if draws['combo']:
            return 'combo_draw'
        if draws['flush']:
            return 'flush_draw'
        if draws['oesd']:
            return 'oesd'
        if draws['gutshot']:
            return 'gutshot'
        if max(mr) >= 12:
            return 'overcards'
        return 'nothing'

    def _equity(self, cs: PokerState, gi: GameInfo) -> float:
        if not cs.board:
            # The table uses rank first and c/d/h/s suit order for ties.
            h1, h2 = cs.my_hand
            return self.eq_tbl.get(_eq_key(h1, h2), 0.50)

        opp_known = cs.opp_revealed_cards or []
        seen = set(cs.my_hand + cs.board + opp_known)
        deck = [self.e7[c] for c in self.all_cards if c not in seen]
        my = [self.e7[c] for c in cs.my_hand]
        brd = [self.e7[c] for c in cs.board]
        opp_k = [self.e7[c] for c in opp_known]
        opp_draw = 2 - len(opp_k)
        brd_draw = 5 - len(brd)

        # One revealed river card leaves a small enough state space to enumerate.
        if brd_draw == 0 and opp_draw == 1:
            w = d = 0
            for c in deck:
                opp_h = opp_k + [c]
                hr = eval7.evaluate(my + brd)
                vr = eval7.evaluate(opp_h + brd)
                if hr > vr: w += 1
                elif hr == vr: d += 1
            return (w + 0.5 * d) / max(1, len(deck))

        # Reduce simulation count as the match time budget is consumed.
        t = gi.time_bank
        if brd_draw == 0:  # river, no known card
            N = 600 if t > 15 else (350 if t > 8 else 120)
        elif brd_draw == 1:  # turn
            N = (650 if t > 15 else (400 if t > 10 else 180)) if opp_known else \
                (550 if t > 15 else (320 if t > 8 else 130))
        else:  # flop
            N = (600 if t > 15 else (350 if t > 10 else 140)) if opp_known else \
                (500 if t > 15 else (280 if t > 8 else 90))

        total = opp_draw + brd_draw
        w = d = 0
        for _ in range(N):
            drawn = random.sample(deck, total)
            opp_h = opp_k + drawn[:opp_draw]
            fb = brd + drawn[opp_draw:]
            hr = eval7.evaluate(my + fb)
            vr = eval7.evaluate(opp_h + fb)
            if hr > vr: w += 1
            elif hr == vr: d += 1
        return (w + 0.5 * d) / N

    def get_move(self, gi: GameInfo, cs: PokerState):
        street = cs.street
        pot = cs.pot
        cost = cs.cost_to_call
        my_chips = cs.my_chips
        my_wager = cs.my_wager
        opp_all_in = cs.opp_chips == 0

        # Auction.
        if street == 'auction':
            self.pot_at_auction = pot
            self.chips_before_auction = my_chips
            eq = self._equity(cs, gi)

            exp_pot = pot * 2.5 + 100

            if eq > 0.72:
                bid = int(exp_pot * random.uniform(0.18, 0.30))
            elif eq > 0.56:
                bid = int(exp_pot * random.uniform(0.14, 0.24))
            elif eq > 0.42:
                bid = int(exp_pot * random.uniform(0.10, 0.20))
            elif eq > 0.33:
                bid = int(exp_pot * random.uniform(0.06, 0.14))
            else:
                bid = int(exp_pot * random.uniform(0.03, 0.08))

            bid = max(0, min(bid, my_chips))
            self.my_bid = bid
            return ActionBid(bid)

        # Information state.
        has_info = bool(cs.opp_revealed_cards)
        if has_info and self.seen_opp_card is None:
            self.seen_opp_card = cs.opp_revealed_cards[0]
        if not self.auction_done and street in ('flop', 'turn', 'river'):
            if self.pot_at_auction > 0:
                self.auction_done = True
                if not has_info and self.my_bid > 0:
                    self.opp_has_info = True
                if self.chips_before_auction is not None:
                    my_cost = self.chips_before_auction - my_chips
                    if my_cost > 0 and has_info:
                        self.opp_bid_history.append(my_cost)
                    elif my_cost == 0 and self.opp_has_info:
                        est = max(self.my_bid + 5, self.my_bid * 1.5)
                        self.opp_bid_history.append(est)
                    elif my_cost > 0 and not has_info:
                        self.opp_bid_history.append(my_cost)
                    if self.opp_bid_history:
                        recent = self.opp_bid_history[-80:]
                        self.opp_bid_avg = sum(recent) / len(recent)

        # Equity and hand classification.
        eq = self._equity(cs, gi)
        hc = self._classify(cs.my_hand, cs.board) if cs.board else 'preflop'
        tex = self._tex(cs.board) if cs.board else {}
        dr = self._draws(cs.my_hand, cs.board) if cs.board and len(cs.board) < 5 else \
            {'flush': False, 'oesd': False, 'gutshot': False, 'combo': False}

        p_odds = cost / (pot + cost) if cost > 0 else 0.0
        adj = eq
        is_draw = hc in ('flush_draw', 'oesd', 'gutshot', 'combo_draw')
        is_strong = hc in ('set', 'two_pair', 'overpair', 'tpgk', 'straight', 'flush', 'straight_flush')
        spr = my_chips / max(1, pot)

        # All-in decisions are determined directly by pot odds.
        if opp_all_in and cost > 0:
            threshold = p_odds + (0.00 if has_info else 0.02)
            if eq > threshold:
                return ActionCall() if cs.can_act(ActionCall) else ActionCheck()
            else:
                return ActionFold() if cs.can_act(ActionFold) else ActionCheck()

        # Facing a bet.
        if cost > 0:
            if not cs.board:
                cf = cost / STACK
                if   cf > 0.28 and eq < 0.84: adj *= 0.68
                elif cf > 0.14 and eq < 0.78: adj *= 0.82
                elif cf > 0.06 and eq < 0.70: adj *= 0.85
                elif cf > 0.025 and eq < 0.63: adj *= 0.90
            else:
                pot_b = max(1, pot - cost)
                br = cost / pot_b
                xp = 0.0
                if tex.get('paired'):   xp += 0.05
                if tex.get('monotone'): xp += 0.05
                if tex.get('trips'):    xp += 0.10

                if street == 'river':
                    if   br > 1.5  and eq < 0.95: adj *= max(0.20, 0.35 - xp)
                    elif br > 0.75 and eq < 0.90: adj *= max(0.30, 0.50 - xp)
                    elif br > 0.35 and eq < 0.82: adj *= max(0.42, 0.70 - xp)
                elif street == 'turn':
                    if   br > 1.5  and eq < 0.93: adj *= max(0.25, 0.40 - xp)
                    elif br > 0.75 and eq < 0.88: adj *= max(0.36, 0.58 - xp)
                    elif br > 0.35 and eq < 0.78: adj *= max(0.52, 0.80 - xp)
                else:  # flop
                    if   br > 1.5  and eq < 0.92: adj *= max(0.32, 0.48 - xp)
                    elif br > 0.75 and eq < 0.86: adj *= max(0.42, 0.65 - xp)
                    elif br > 0.35 and eq < 0.78: adj *= max(0.55, 0.84 - xp)

                if street == 'river' and my_wager > 0 and cost > 0:
                    if eq < 0.93: adj *= 0.30

                if street == 'turn' and br > 1.0 and eq < 0.87:
                    adj *= 0.38

                if self.opp_has_info and not has_info:
                    if br > 0.20 and eq < 0.90:
                        adj *= 0.60

                if is_draw and street != 'river':
                    bonus = 0.12 if dr['combo'] else (0.08 if dr['flush'] else
                            0.07 if dr['oesd'] else 0.04)
                    adj = min(eq, adj + bonus)

                if br > 3.0 and not is_draw:
                    if is_strong or hc in ('top_pair', 'overpair'):
                        catch_freq = 0.30 if br > 8.0 else 0.22
                        if random.random() < catch_freq:
                            return ActionCall() if cs.can_act(ActionCall) else ActionCheck()
                    elif hc in ('mid_pair', 'underpair', 'two_pair'):
                        catch_freq = 0.15 if br > 8.0 else 0.10
                        if random.random() < catch_freq:
                            return ActionCall() if cs.can_act(ActionCall) else ActionCheck()

            if self.call_scale < 1.0:
                rec = (eq - adj) * (1.0 - self.call_scale) * 0.55
                adj = min(eq, adj + rec)

            if has_info and adj < eq:
                if cost > 0 and my_wager > 0:
                    adj = adj * 0.75 + eq * 0.25
                elif cost > 0:
                    adj = adj * 0.55 + eq * 0.45
                else:
                    adj = adj * 0.05 + eq * 0.95

        # Pot commitment.
        commit = my_wager / STACK
        proj_inv = my_wager + cost

        if has_info and cs.board and cost > 0:
            is_monster = hc in ('set', 'two_pair', 'straight', 'flush', 'straight_flush')
            if not is_monster:
                max_invest = int(STACK * 0.25)
                if proj_inv > max_invest and eq < 0.90:
                    if cs.can_act(ActionFold):
                        return ActionFold()
                    return ActionCheck() if cs.can_act(ActionCheck) else ActionCall()

        if pot > 700 or proj_inv > 250:
            floor = max(p_odds, 0.54)
            if (commit > 0.22 or pot > 2200) and cost < pot * 0.10:
                floor = p_odds
            if spr < 1.5 and cost < pot * 0.5:
                floor = max(p_odds, 0.38)
            if commit > 0.55 and cost < pot * 0.25:
                floor = max(p_odds, 0.28)
            if tex.get('paired') and cost > pot * 0.38 and eq < 0.89:
                floor = max(floor, 0.60)
            if tex.get('trips') and cost > pot * 0.30 and eq < 0.93:
                floor = max(floor, 0.67)
            if adj < floor:
                if cost > 0 and cs.can_act(ActionFold):
                    return ActionFold()
                return ActionCheck() if cs.can_act(ActionCheck) else ActionCall()

        # Preflop fold gate.
        if not cs.board and cost > 0:
            cr = cost / STACK
            if cs.is_bb:
                gate = 0.39 + min(0.12, cr * 0.40)
            else:
                gate = 0.43 + min(0.12, cr * 0.40)
            if adj < gate:
                if cs.can_act(ActionFold):
                    return ActionFold()
                return ActionCheck() if cs.can_act(ActionCheck) else ActionCall()

        # Raising.
        if cs.can_act(ActionRaise):
            rlo, rhi = cs.raise_bounds

            if not cs.board:
                if cost > 0 and my_wager > 40 and cost > 600:
                    if eq > 0.79:
                        tgt = my_wager + cost + int(pot * random.uniform(2.0, 3.0))
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))
                elif adj < 0.73 and my_wager > 80:
                    pass
                elif adj > 0.80:
                    tgt = my_wager + cost + int(pot * random.uniform(3.0, 4.5))
                    return ActionRaise(int(max(rlo, min(tgt, rhi))))
                elif adj > 0.64 and cost <= 20:
                    tgt = my_wager + cost + int(pot * random.uniform(2.5, 3.5))
                    return ActionRaise(int(max(rlo, min(tgt, rhi))))
                elif adj > 0.52 and cost <= 20:
                    tgt = my_wager + cost + int(pot * random.uniform(2.0, 3.0))
                    return ActionRaise(int(max(rlo, min(tgt, rhi))))

            elif street == 'river':
                if cost == 0:
                    if has_info and adj > 0.52:
                        sz = random.uniform(0.28, 0.40)
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))
                    elif adj > 0.78:
                        sz = random.uniform(0.55, 0.90) + self.aggro_boost * 0.50
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))
                    elif adj > 0.62:
                        sz = random.uniform(0.40, 0.65) + self.aggro_boost * 0.25
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))
                    elif adj < 0.42:
                        bf = min(0.30, 0.12 + self.opp_fold_rate * 0.45 + self.aggro_boost * 0.25)
                        if self.opp_has_info and not has_info:
                            bf *= 0.01
                        if random.random() < bf:
                            sz = random.uniform(0.55, 0.80)
                            tgt = my_wager + int(pot * sz)
                            return ActionRaise(int(max(rlo, min(tgt, rhi))))
                else:
                    if adj > 0.88 and not (has_info and my_wager > 0):
                        sz = random.uniform(2.8, 4.5)
                        tgt = my_wager + cost + int(cost * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))

            else:
                info_reraise_ok = True
                if has_info and cost > 0 and my_wager > 0:
                    if hc not in ('set', 'two_pair', 'straight', 'flush', 'straight_flush') or eq < 0.85:
                        info_reraise_ok = False

                if cost > 0 and adj > 0.88 and info_reraise_ok:
                    cr_freq = 0.30 if not cs.is_bb else 0.22
                    if random.random() < cr_freq:
                        sz = random.uniform(2.8, 4.0)
                        tgt = my_wager + cost + int(cost * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))

                if cost > 0 and adj > 0.78 and info_reraise_ok:
                    sz = random.uniform(2.8, 4.0)
                    tgt = my_wager + cost + int(cost * sz)
                    if has_info: tgt = int(tgt * 0.85)
                    return ActionRaise(int(max(rlo, min(tgt, rhi))))

                if cost == 0:
                    if adj > 0.96 and random.random() < 0.04:
                        return ActionCheck()

                    if adj > 0.68:
                        sz = random.uniform(0.70, 1.25) + self.aggro_boost * 0.45
                        if is_strong: sz *= 1.25
                        if tex.get('paired') and eq < 0.93: sz *= 0.55
                        if tex.get('trips') and eq < 0.96: sz *= 0.40
                        if has_info: sz = random.uniform(0.30, 0.45)
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))

                    elif adj > 0.52:
                        sz = random.uniform(0.40, 0.65) + self.aggro_boost * 0.25
                        if has_info: sz = random.uniform(0.25, 0.38)
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))

                    elif adj > 0.50:
                        sz = random.uniform(0.28, 0.45) + self.aggro_boost * 0.15
                        tgt = my_wager + int(pot * sz)
                        return ActionRaise(int(max(rlo, min(tgt, rhi))))

                    elif is_draw and eq > 0.20:
                        sb = 0.75 if dr['combo'] else (0.60 if dr['flush'] else
                             0.55 if dr['oesd'] else 0.38)
                        sb += self.aggro_boost * 0.40
                        if self.opp_has_info and not has_info:
                            sb *= 0.05
                        if random.random() < sb:
                            sz = random.uniform(0.55, 0.90)
                            tgt = my_wager + int(pot * sz)
                            return ActionRaise(int(max(rlo, min(tgt, rhi))))

                    elif adj < 0.40:
                        bf = min(0.24, 0.08 + self.opp_fold_rate * 0.45)
                        if self.opp_has_info and not has_info:
                            bf *= 0.01
                        if tex.get('ace_high'): bf *= 1.5
                        if pot < 400 and random.random() < bf:
                            tgt = my_wager + int(pot * random.uniform(0.55, 0.85))
                            return ActionRaise(int(max(rlo, min(tgt, rhi))))

        # Call or fold.
        if cost > 0:
            if is_draw and street != 'river' and adj < p_odds:
                bonus = 0.10 if dr['combo'] else (0.07 if dr['flush'] else
                        0.06 if dr['oesd'] else 0.03)
                adj = min(eq, adj + bonus)

            if has_info:
                margin = 0.001
            elif self.opp_has_info:
                margin = 0.12
            else:
                if street == 'river':
                    margin = 0.06
                elif street == 'turn':
                    margin = 0.045
                else:
                    margin = 0.035

            pip = min(0.06, pot / 5500.0)

            if adj > (p_odds + margin + pip):
                return ActionCall() if cs.can_act(ActionCall) else ActionCheck()
            else:
                return ActionFold() if cs.can_act(ActionFold) else ActionCheck()

        return ActionCheck() if cs.can_act(ActionCheck) else ActionFold()


if __name__ == '__main__':
    run_bot(DominatorBot(), parse_args())
