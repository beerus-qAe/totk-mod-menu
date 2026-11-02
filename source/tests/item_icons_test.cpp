// Validate the real private icon cache in a headless ImGui font atlas.
#include <cassert>
#include <cstdio>
#include "imgui.h"
#include "modmenu/runtime/ui/item_icons.h"
int main(){
    ImGui::CreateContext();auto &io=ImGui::GetIO();io.IniFilename=nullptr;
    io.DisplaySize=ImVec2(800,600);io.DeltaTime=1.f/60;
    for(int rebuild=0;rebuild<2;++rebuild){
        io.Fonts->Clear();io.Fonts->AddFontDefault();item_icons_build(io.Fonts);
        assert(io.Fonts->TexPixelsRGBA32 && io.Fonts->TexWidth>=2028 && io.Fonts->TexHeight>=1612);
        io.Fonts->SetTexID((ImTextureID)1234);
        for(int frame=0;frame<2;++frame){
            ImGui::NewFrame();ImGui::Begin("Icon cache test");
            ImVec2 at=ImGui::GetCursorScreenPos();
            assert(item_icons_draw("Item_Fruit_A",at,48));
            assert(item_icons_draw("SpObj_Cannon_Capsule_A_01",ImVec2(at.x+50,at.y),48));
            assert(item_icons_draw("BombFruit",ImVec2(at.x+100,at.y),48));
            assert(!item_icons_draw("NonexistentIcon",at,48));
            ImGui::Dummy(ImVec2(160,60));ImGui::End();ImGui::Render();
            if(frame)assert(ImGui::GetDrawData()->TotalVtxCount>0);
        }
    }
    ImGui::DestroyContext();puts("REAL_ICON_CACHE_CHECK_OK: real textures, missing fallback, font rebuild, draw commands");
}
