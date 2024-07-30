import os
import io
from odoo import models, fields, api
import base64
import pandas as pd

class ColorCodeImportWizard(models.TransientModel):
    _name = 'color.code.import.wizard'
    _description = 'Wizard for importing color code'

    database_attachment = fields.Binary(string='Database Attachment', required=True)

    #Import categories from all the products
    def import_color_code(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0,
                               dtype={'EAN': str, 'Article number short': str, 'Article number long': str})

            for _, row in df.iterrows():
                color_name = row['Color_Name']
                color_code = row['Color_Code']

                # Buscar el registro de color correspondiente
                color_record = self.env['product.attribute.value'].search([('name', '=', color_name)], limit=1)

                # Si se encuentra el registro de color, actualizar el campo color_code
                if color_record:
                    color_record.write({'color_code': color_code})
