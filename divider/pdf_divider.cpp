#include <pybind11/pybind11.h>
#include <poppler-document.h>
#include <poppler-page.h>
#include <poppler-page-renderer.h>

namespace py = pybind11;

void divide_pdf(const std::string& input_path, const std::string& output_path, int start_page, int end_page) {
    auto doc = poppler::document::load_from_file(input_path);
    if (!doc) {
        throw std::runtime_error("Falha ao abrir o PDF.");
    }

    for (int i = start_page - 1; i < end_page; ++i) {
        auto page = doc->create_page(i);
        if (page) {
            page->save(output_path + "_page_" + std::to_string(i + 1) + ".pdf", nullptr, {});
        }
    }
}

PYBIND11_MODULE(pdf_divider, m) {
    m.def("divide_pdf", &divide_pdf, "Divide um PDF em páginas separadas");
}
