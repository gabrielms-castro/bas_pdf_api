
from divider.dividers import EprocPdfDivider, GeneralPdfDivider


class PdfDividerFactory:

    @staticmethod
    def get_divider(sistema_processual):
        if sistema_processual.lower() == "eproc":
            return EprocPdfDivider()
        else:
            return GeneralPdfDivider()