#include "item_icons.h"
#include <cstdint>
#include <cstring>
#include <fstream>
#include <string>
#include <unordered_map>
#include <vector>

namespace {
bool loaded,ready;
uint32_t edge,cell,tile;
ImVec2 origin,texture_size;
std::vector<unsigned char> pixels;
std::unordered_map<std::string,unsigned> indices;
void load() {
    loaded=true;
    std::ifstream input("item-icons.rgba",std::ios::binary);
    char magic[8];uint32_t header[4];
    if(!input.read(magic,8) || memcmp(magic,"ITICONS1",8) || !input.read((char *)header,16))return;
    edge=header[0];cell=header[1];tile=header[2];
    if(edge<64 || edge>4096 || cell<8 || tile<4 || tile+4>cell || cell>edge || header[3]>(edge/cell)*(edge/cell))return;
    pixels.resize((size_t)edge*edge*4);
    if(!input.read((char *)pixels.data(),pixels.size())){pixels.clear();return;}
    std::ifstream map("item-icons.tsv");std::string line;
    while(std::getline(map,line)) {
        auto tab=line.find('\t');if(tab==std::string::npos)continue;
        try {unsigned index=(unsigned)std::stoul(line.substr(tab+1));if(index<header[3])indices[line.substr(0,tab)]=index;}
        catch(...) {}
    }
}
}

void item_icons_build(ImFontAtlas *atlas) {
    ready=false;
    if(!loaded)load();
    if(pixels.empty() || indices.empty())return;
    unsigned columns=edge/cell,maximum=0;
    for(const auto &entry:indices)if(entry.second>maximum)maximum=entry.second;
    unsigned used_width=columns*cell,used_height=(maximum/columns+1)*cell;
    // Leave room for ImGui's packing padding; a 2048-wide rect cannot fit in
    // a 2048-wide font texture once the one-pixel padding is added.
    int index=atlas->AddCustomRectRegular((int)used_width,(int)used_height);
    unsigned char *rgba=nullptr;int w=0,h=0;
    atlas->GetTexDataAsRGBA32(&rgba,&w,&h);
    const ImFontAtlasCustomRect *rect=atlas->GetCustomRectByIndex(index);
    if(!rgba || !rect->IsPacked() || rect->X+used_width>(unsigned)w || rect->Y+used_height>(unsigned)h)return;
    for(unsigned y=0;y<used_height;++y)
        memcpy(rgba+((size_t)(rect->Y+y)*w+rect->X)*4,pixels.data()+(size_t)y*edge*4,(size_t)used_width*4);
    origin=ImVec2((float)rect->X,(float)rect->Y);texture_size=ImVec2((float)w,(float)h);ready=true;
}

bool item_icons_draw(const char *actor,ImVec2 position,float size) {
    auto found=indices.find(actor);
    if(!ready || found==indices.end())return false;
    unsigned index=found->second,columns=edge/cell;
    float x=origin.x+(index%columns)*cell+2,y=origin.y+(index/columns)*cell+2;
    ImVec2 uv0(x/texture_size.x,y/texture_size.y),uv1((x+tile)/texture_size.x,(y+tile)/texture_size.y);
    ImGui::GetWindowDrawList()->AddImage(ImGui::GetIO().Fonts->TexID,position,ImVec2(position.x+size,position.y+size),uv0,uv1);
    return true;
}
