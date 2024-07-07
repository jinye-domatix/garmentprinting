from odoo import models, fields

class SaleMod(models.Model):
    _inherit = 'product.template'

    supplier_article_code = fields.Char(string='Supplier Article Code')
    short_article_number = fields.Char(string='Short Article Number')