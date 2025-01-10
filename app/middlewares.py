import glob
import logging
import os
import shutil
from django.conf import settings

logging.basicConfig(level=logging.INFO)

class CleanTempMiddleware:
    """
    Middleware para limpar arquivos temporários na pasta TEMP_DIR após cada requisição.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.temp_dir = settings.TEMP_DIR  # Agora usando o TEMP_DIR do settings
        os.makedirs(self.temp_dir, exist_ok=True)

    def __call__(self, request):
        response = self.get_response(request)
        self.clean_temp_folder()
        return response

    def clean_temp_folder(self):
        try:
            for arquivo in glob.glob(f"{self.temp_dir}/*"):
                if os.path.isfile(arquivo):
                    os.remove(arquivo)
                elif os.path.isdir(arquivo):
                    shutil.rmtree(arquivo)
            logging.info(f"Arquivos temporários limpos em {self.temp_dir}")
        except Exception as e:
            logging.error(f"Erro ao limpar arquivos temporários: {e}")
