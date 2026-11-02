// Private inventory browser with cached real icons and queued item delivery.
#include "imgui.h"
#include "items_window.h"
#include <algorithm>
#include <fstream>
#include <string>
#include <vector>
#ifdef ITEM_ICONS_ENABLED
#include "item_icons.h"
#endif
#ifdef SPAWN_MENU_MODE
#include "modmenu/runtime/spawn/spawn_menu.h"
#endif

namespace {
struct Item { std::string category, id, name; };
std::vector<Item> items;
std::vector<int> matches;
bool loaded, requested, modal;
char search[192] = {};
int category, selected = -1, quantity = 1;
const char *categories[] = {"Todas", "Armas", "Arcos", "Escudos", "Armaduras", "Materiais", "Dispositivos Zonai", "Flechas", "Objetos Zonai", "Energia Zonai", "Tecidos", "Equipamento de cavalo", "Moedas", "Itens especiais", "Alimentos"};

std::string folded(std::string value) {
    std::string result;
    for (size_t i = 0; i < value.size(); ++i) {
        unsigned char c = value[i];
        if (c == 0xc3 && i + 1 < value.size()) {
            unsigned char next = value[i + 1];
            unsigned char lower = next < 0xa0 ? next + 0x20 : next;
            char plain = lower >= 0xa0 && lower <= 0xa5 ? 'a'
                       : lower == 0xa7 ? 'c'
                       : lower >= 0xa8 && lower <= 0xab ? 'e'
                       : lower >= 0xac && lower <= 0xaf ? 'i'
                       : lower >= 0xb2 && lower <= 0xb6 ? 'o'
                       : lower >= 0xb9 && lower <= 0xbc ? 'u' : 0;
            if (plain) { result += plain; ++i; continue; }
        }
        result += c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c;
    }
    return result;
}
void filter() {
    matches.clear();
    const auto query = folded(search);
    for (int i = 0; i < (int)items.size(); ++i) {
        const auto &item = items[i];
        if (category && item.category != categories[category]) continue;
        std::string aliases=item.id=="BombFruit" ? " flecha explosiva flechas explosivas bomba explosivo" : "";
        if (folded(item.name + " " + item.id + " " + item.category+aliases).find(query) != std::string::npos) matches.push_back(i);
    }
}
void load() {
    loaded = true;
    std::ifstream input("items.tsv", std::ios::binary);
    std::string line;
    while (std::getline(input, line) && items.size() < 20000) {
        if (line.empty() || line[0] == '#' || line.size() > 1024) continue;
        if (line.back() == '\r') line.pop_back();
        auto a = line.find('\t'), b = a == std::string::npos ? a : line.find('\t', a + 1);
        if (a == std::string::npos || b == std::string::npos || a == 0 || b == a + 1 || b + 1 == line.size()) continue;
        items.push_back({line.substr(0, a), line.substr(a + 1, b - a - 1), line.substr(b + 1)});
    }
    filter();
}
}

void items_button() {
    if (ImGui::Button("Adicionar itens...")) requested = true;
}

bool items_modal() { return modal || requested; }

void items_window(float scale) {
    if (requested) {
        if (!loaded) load();
        ImGui::OpenPopup("Adicionar itens###items");
        requested = false;
    }
    bool open = true;
    const ImVec2 screen = ImGui::GetIO().DisplaySize;
    ImGui::SetNextWindowSize(ImVec2(std::min(900.f * scale, screen.x * .9f),
                                   std::min(650.f * scale, screen.y * .85f)), ImGuiCond_Appearing);
    ImGui::SetNextWindowPos(ImVec2(screen.x / 2, screen.y / 2), ImGuiCond_Appearing, ImVec2(.5f, .5f));
    modal = ImGui::BeginPopupModal("Adicionar itens###items", &open, ImGuiWindowFlags_NoSavedSettings);
    if (!modal) return;
#ifdef SPAWN_BETA_CATALOG
#ifdef SPAWN_FRAME_QUEUE
    ImGui::TextDisabled(MODMENU_BETA_LABEL " | Um item por clique | Vestuario por bau");
#else
    ImGui::TextDisabled("Beta 0.1 | Um item por clique | Vestuario por bau");
#endif
#endif
    if (ImGui::IsWindowAppearing()) ImGui::SetKeyboardFocusHere();
    bool changed = ImGui::InputTextWithHint("Buscar", "Nome ou ID interno", search, sizeof search);
    changed |= ImGui::Combo("Categoria", &category, categories, IM_ARRAYSIZE(categories));
    if (changed) filter();
    ImGui::Text("%d resultados", (int)matches.size());
    if (items.empty()) ImGui::TextWrapped("Catalogo indisponivel. Coloque items.tsv ao lado de totk.exe.");
    if (ImGui::BeginChild("##results", ImVec2(0, -170 * scale), ImGuiChildFlags_Borders)) {
        ImGuiListClipper clipper;
        clipper.Begin((int)matches.size());
        while (clipper.Step()) for (int row = clipper.DisplayStart; row < clipper.DisplayEnd; ++row) {
            int index = matches[row];
            const auto &item = items[index];
            ImGui::PushID(index);
#ifdef ITEM_ICONS_ENABLED
            float icon_size=48.f*scale;
            ImVec2 at=ImGui::GetCursorScreenPos();
            if(!item_icons_draw(item.id.c_str(),at,icon_size)) {
                ImGui::GetWindowDrawList()->AddRect(at,ImVec2(at.x+icon_size,at.y+icon_size),IM_COL32(100,100,100,255));
                ImGui::GetWindowDrawList()->AddText(ImVec2(at.x+icon_size*.35f,at.y+icon_size*.2f),IM_COL32(150,150,150,255),"?");
            }
            ImGui::Dummy(ImVec2(icon_size,icon_size));ImGui::SameLine();
            if (ImGui::Selectable((item.name + "\n" + item.id).c_str(), selected == index,0,ImVec2(0,ImGui::GetFontSize()*2+4*scale))) {
#else
            if (ImGui::Selectable((item.name + "  |  " + item.id).c_str(), selected == index)) {
#endif
                selected = index;
                quantity = 1;
            }
            ImGui::PopID();
        }
    }
    ImGui::EndChild();
    if (selected >= 0) {
        const auto &item = items[selected];
        ImGui::TextWrapped("Selecionado: %s (%s)", item.name.c_str(), item.id.c_str());
#ifdef SPAWN_MENU_MODE
        const bool stack = false; // first live menu validation creates exactly one apple
#else
        const bool stack = item.category == "Materiais" || item.category == "Dispositivos Zonai";
#endif
        ImGui::BeginDisabled(!stack);
        ImGui::InputInt("Quantidade", &quantity);
        ImGui::EndDisabled();
        quantity = stack ? std::clamp(quantity, 1, 999) : 1;
    }
#ifdef SPAWN_MENU_MODE
    bool supported=selected>=0 && spawn_menu_item_support(items[selected].id.c_str());
    ImGui::BeginDisabled(!supported || spawn_menu_busy());
    const bool chest=selected>=0 && spawn_menu_item_chest(items[selected].id.c_str());
    if(ImGui::Button(chest ? "Criar bau com este item" : "Criar 1 item perto do Link"))spawn_menu_submit(items[selected].id.c_str());
    ImGui::EndDisabled();
    ImGui::TextWrapped("%s",spawn_menu_status());
    if(selected>=0 && !supported)ImGui::TextWrapped("Este item ainda nao foi validado para criacao.");
    if(selected>=0 && spawn_menu_item_support(items[selected].id.c_str())==2)ImGui::TextWrapped("Beta: este item ainda nao foi testado individualmente.");
    if(chest)ImGui::TextWrapped("Abra o bau criado perto do Link para receber o item.");
    if(selected>=0 && items[selected].id=="BombFruit")ImGui::TextWrapped("Flor-bomba: material para combinar com uma flecha e obter o efeito explosivo.");
    if(selected>=0 && items[selected].category=="Objetos Zonai")ImGui::TextWrapped("Dispositivo montado. Para guardar no inventario, escolha a versao em capsula.");
#else
    ImGui::TextWrapped("Criacao disponivel na compilacao com integracao do modmenu.");
#endif
    if (ImGui::Button("Voltar") || ImGui::IsKeyPressed(ImGuiKey_Escape, false) ||
        ImGui::IsKeyPressed(ImGuiKey_GamepadFaceRight, false)) ImGui::CloseCurrentPopup();
    ImGui::EndPopup();
}
