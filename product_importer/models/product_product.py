from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    color_code = fields.Char(string='Color Code')
