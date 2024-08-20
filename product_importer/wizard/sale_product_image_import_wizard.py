import base64
import pandas as pd
import io
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.misc import file_path


class ImportProductsWizard(models.TransientModel):
    _name = 'sale.product.image.import.wizard'
    _description = 'Import Products Wizard'

    database_attachment = fields.Binary('Database Attachment', required=True)

    def import_images(self):
        if not self.database_attachment:
            raise UserError("No file attached.")

        data = base64.b64decode(self.database_attachment)
        excel_data = io.BytesIO(data)
        xls = pd.ExcelFile(excel_data)

        first_image_assigned = {}

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, dtype={'Article number short with point': str})

            df.sort_values(by=['Article number short with point', 'Image Sequence number'], inplace=True)

            for index, row in df.iterrows():
                article_number = row['Article number short with point']
                color_code = row['Image color number']
                if color_code != '-':
                    color_code = int(row['Image color number'])
                else:
                    color_code = ''
                image_name = row['File Name']
                image_path = None
                try:
                    image_path = file_path(f'product_importer/data/Product_Image1/{image_name}')
                except FileNotFoundError:
                    print(f"No se encontró el archivo de imagen en {image_path}")
                    continue

                product = self.env['product.template'].search([('short_article_number', '=', article_number)], limit=1)
                if not product:
                    print(f"Product with article number {article_number} not found.")
                    continue
                color_product_variant_ids = product.product_variant_ids.filtered(lambda p: p.color_code == str(color_code))
                if color_product_variant_ids:
                    for color_product_variant_id in color_product_variant_ids:
                        try:
                            with open(image_path, 'rb') as image_file:
                                image_data = base64.b64encode(image_file.read())
                        except IOError as e:
                            print(f"Error: {e}")
                            continue

                        color_product_variant_id.image_1920 = image_data
                        self.env.cr.commit()
                else:
                    existing_image = self.env['product.image'].search([('product_tmpl_id', '=', product.id), ('name', '=', image_name)], limit=1)
                    if existing_image:
                        print(f"Image {image_name} already exists for product {product.name}, skipping...")
                        continue

                    try:
                        with open(image_path, 'rb') as image_file:
                            image_data = base64.b64encode(image_file.read())
                    except IOError as e:
                        print(f"Error: {e}")
                        continue

                    new_image = self.env['product.image'].create({
                        'product_tmpl_id': product.id,
                        'image_1920': image_data,
                        'name': image_name
                    })
                    self.env.cr.commit()

                    print(f"Imported image for product {product.name}")

                    if not first_image_assigned.get(article_number):
                        product.image_1920 = new_image.image_1920
                        first_image_assigned[article_number] = True
                        print(f"Updated main image for {product.name}")

