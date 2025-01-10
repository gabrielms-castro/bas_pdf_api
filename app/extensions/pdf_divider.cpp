#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <poppler-document.h>
#include <poppler-page.h>
#include <poppler-page-renderer.h>
#include <cairo/cairo.h>
#include <cairo/cairo-pdf.h>
#include <filesystem>
#include <iostream>
#include <vector>

namespace py = pybind11;
namespace fs = std::filesystem;

// Função para converter imagem RGB para escala de cinza
std::vector<unsigned char> convert_to_gray(poppler::image img) {
    int width = img.width();
    int height = img.height();
    int bytes_per_row = img.bytes_per_row();

    std::vector<unsigned char> gray_data(width * height);

    // Acessando os dados da imagem de forma segura
    unsigned char* data = reinterpret_cast<unsigned char*>(img.data());

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int index = y * bytes_per_row + x * 3;
            unsigned char r = data[index];
            unsigned char g = data[index + 1];
            unsigned char b = data[index + 2];
            unsigned char gray = static_cast<unsigned char>(0.299 * r + 0.587 * g + 0.114 * b);
            gray_data[y * width + x] = gray;
        }
    }

    return gray_data;
}

void divide_pdf(const std::string &input_path, const std::string &output_dir, std::vector<std::tuple<int, int, std::string>> events) {
    auto doc = poppler::document::load_from_file(input_path);
    if (!doc) {
        throw std::runtime_error("Erro ao abrir o PDF.");
    }

    std::cout << "Processando PDF: " << input_path << std::endl;

    if (!fs::exists(output_dir)) {
        fs::create_directories(output_dir);
    }

    poppler::page_renderer renderer;
    renderer.set_render_hint(poppler::page_renderer::text_antialiasing);
    renderer.set_render_hint(poppler::page_renderer::text_hinting);

    for (const auto& [start_page, end_page, output_file] : events) {
        std::string output_path = output_dir + "/" + output_file;
        std::cout << "Criando arquivo: " << output_path << " (Páginas " << start_page << " a " << end_page << ")" << std::endl;

        cairo_surface_t *surface = cairo_pdf_surface_create(output_path.c_str(), 595, 842);
        cairo_t *cr = cairo_create(surface);

        for (int i = start_page - 1; i < end_page; ++i) {
            auto page = doc->create_page(i);
            if (!page) continue;

            poppler::image img = renderer.render_page(page, 96, 96);

            // Converter a imagem para escala de cinza
            std::vector<unsigned char> gray_data = convert_to_gray(img);

            cairo_surface_t *image_surface = cairo_image_surface_create_for_data(
                gray_data.data(),
                CAIRO_FORMAT_A8,
                img.width(),
                img.height(),
                img.width()
            );

            if (!image_surface) continue;

            cairo_set_source_surface(cr, image_surface, 0, 0);
            cairo_paint(cr);
            cairo_surface_destroy(image_surface);
        }

        cairo_destroy(cr);
        cairo_surface_finish(surface);
        cairo_surface_destroy(surface);
    }

    std::cout << "Divisão concluída!" << std::endl;
}

PYBIND11_MODULE(pdf_divider, m) {
    m.def("divide_pdf", &divide_pdf, "Divide um PDF em múltiplos PDFs separados com base nos eventos");
}
