// Headless UI checks using synthetic catalog data, without running the game.
#include <cassert>
#include <cstdio>
#include <cstring>
#ifdef SPAWN_MENU_MODE
extern "C" int spawn_menu_submit(const char *actor) { return !strcmp(actor,"Item_Fruit_A"); }
extern "C" int spawn_menu_busy(void) { return 0; }
extern "C" const char *spawn_menu_status(void) { return "Synthetic UI test"; }
#endif
#include "../modmenu/runtime/ui/items_window.cpp"

int main() {
    assert(folded("FÔLEGO, Maçã, AÇÃO") == "folego, maca, acao");
    items = {{"Armas", "Test_Sword", "Espada de teste"},
             {"Materiais", "Test_Apple", "Maçã de teste"}};
    strcpy(search, "maca"); filter();
    assert(matches.size() == 1 && matches[0] == 1);
    strcpy(search, "TEST_SWORD"); filter();
    assert(matches.size() == 1 && matches[0] == 0);
    category = 5; filter(); assert(matches.empty());
    category = 0; search[0] = 0; filter(); assert(matches.size() == 2);
    items.push_back({"Flechas","Obj_ArrowNormal_A_01","Flecha"});
    strcpy(search,"flechas");filter();assert(matches.size()==1 && matches[0]==2);
    items.pop_back();search[0]=0;filter();
    items.push_back({"Materiais","BombFruit","Flor-bomba"});
    strcpy(search,"flecha explosiva");filter();assert(matches.size()==1 && matches[0]==2);
    items.pop_back();search[0]=0;filter();

    ImGui::CreateContext();
    auto &io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.DisplaySize = ImVec2(1280, 720);
    io.DeltaTime = 1.f / 60;
    unsigned char *pixels; int width, height;
#ifdef ITEM_ICONS_ENABLED
    item_icons_build(io.Fonts);
#endif
    io.Fonts->GetTexDataAsRGBA32(&pixels, &width, &height);
    loaded = true;
    selected = 1;
    items[1].id = "Item_Fruit_A";
    requested = true;
    for (int frame = 0; frame < 3; ++frame) {
        ImGui::NewFrame();
        ImGui::Begin("Parent");
        items_window(1);
        assert(items_modal());
        ImGui::End();
        ImGui::Render();
        // ImGui hides a newly opened popup for its first sizing frame.
        if (frame > 0) assert(ImGui::GetDrawData()->TotalVtxCount > 0);
    }
    ImGui::DestroyContext();
    puts("ITEM_WINDOW_CHECK_OK: name/ID search, accents, categories, modal layout");
}
