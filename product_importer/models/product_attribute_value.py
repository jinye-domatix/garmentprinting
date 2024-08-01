from odoo import models, fields


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    color_code = fields.Char(
        string='Color Code',
    )