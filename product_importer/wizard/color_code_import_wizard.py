import os
import io
from odoo import models, fields, api
import base64
import pandas as pd

class ColorCodeImportWizard(models.TransientModel):
    _name = 'color.code.import.wizard'
    _description = 'Wizard for importing color code'

    database_attachment = fields.Binary(string='Database Attachment', required=True)

    def import_color_code(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0,
                               dtype={'EAN': str, 'Article number short': str, 'Article number long': str})

            for _, row in df.iterrows():
                article_number_long = row['Article number long']
                color_code = row['Color_Code']

                # Search for the corresponding product
                product_ids = self.env['product.product'].search([('default_code', '=', article_number_long)])

                # If the product is found, update the color_code field
                if product_ids:
                    product_ids.write({'color_code': color_code})
