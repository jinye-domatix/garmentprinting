import os
import io
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import pandas as pd

class SaleProductLanguageImportWizard(models.TransientModel):
    _name = 'sale.product.language.import.wizard'
    _description = 'Wizard for Language Import from Excel'

    database_attachment = fields.Binary(string='Database Attachment', required=True)

    def import_languages(self):
        if self.database_attachment:
            data = base64.b64decode(self.database_attachment)
            excel_data = io.BytesIO(data)
            df = pd.read_excel(excel_data, index_col=None, header=0, dtype={'Article number short with point': str})

            total_rows = len(df.index)
            language_map = {'english': 'en_US', 'german': 'de_DE', 'spanish': 'es_ES'}

            for index, row in df.iterrows():
                if index % 300 == 0:
                    print(index, "IMPORTED LANGUAGES", total_rows)

                product = self.env['product.template'].search([('short_article_number', '=', row['Article number short with point'])], limit=1)
                if not product:
                    product = self.env['product.template'].create({
                        'short_article_number': row['Article number short with point'],
                        'name': row['Article_name'],
                        'description': row['Article_description'],
                    })

                lang_code = language_map.get(row['Language'].lower(), None)
                if lang_code:
                    self.update_field_translation(product, 'name', row['Article_name'], lang_code)
                    self.update_field_translation(product, 'description_sale', row['Article_description'], lang_code)

    def update_field_translation(self, record, field_name, new_content, lang):
        field = record._fields[field_name]
        if not field.translate:
            raise UserError(f"The field {field_name} is not translatable.")
        
        translations = field._get_stored_translations(record) or {}
        translations[lang] = new_content

        record.env.cache.update_raw(
            record, field, [translations], dirty=True
        )
        record.modified([field_name])




