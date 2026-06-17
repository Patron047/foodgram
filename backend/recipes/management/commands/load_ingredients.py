import csv

from django.core.management.base import BaseCommand

from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загружает ингредиенты из CSV без заголовков'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str)

    def handle(self, *args, **options):
        file_path = options['file_path']
        ingredients_count = 0

        with open(file_path, 'r', encoding='utf-8') as csv_file:
            reader = csv.reader(csv_file)
            for row in reader:
                if len(row) < 2:
                    continue
                name = row[0].strip()
                unit = row[1].strip()
                if name and unit:
                    Ingredient.objects.get_or_create(
                        name=name,
                        defaults={'measurement_unit': unit}
                    )
                    ingredients_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Загружено {ingredients_count} ингредиентов')
        )
