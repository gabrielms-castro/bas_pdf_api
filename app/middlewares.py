import glob
import os
import shutil
import logging

logging.basicConfig(level=logging.INFO)

class CleanTempMiddleware:
    """
    Middleware para limpar arquivos temporários na pasta /tmp após cada requisição.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.temp_dir = "/tmp"
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