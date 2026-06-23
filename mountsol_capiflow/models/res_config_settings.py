# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    capiflow_default_rate = fields.Float(
        string='Capiflow Default Rate (%)',
        config_parameter='capiflow.default_rate',
        default=12.0,
        help="Default expected-default rate applied to new bundles.")
