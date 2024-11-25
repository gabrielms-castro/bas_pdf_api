import glob
import os

class CleanTempMiddleware:
    """
    Middleware para limpar arquivos temporários na pasta /tmp após cada requisição.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.limpar_pasta_temp()
        return response

    def limpar_pasta_temp(self):
        temp_dir = "/tmp"
        try:
            for arquivo in glob.glob(f"{temp_dir}/*"):
                if os.path.isfile(arquivo):
                    os.remove(arquivo)
                elif os.path.isdir(arquivo):
                    os.rmdir(arquivo)  # Remove diretórios vazios
        except Exception as e:
            print(f"Erro ao limpar arquivos temporários: {e}")