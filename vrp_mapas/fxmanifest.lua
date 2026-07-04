shared_script '@eqpg-pro/events.lua'
client_script '@eqpg-pro/client_shared.lua'
server_script '@eqpg-pro/server_shared.lua'
fx_version "cerulean"
game "gta5"

lua54 "yes"
author "SallyStark & kokkuri"
description "Coisa feia, dumpando servidor neh safadinho"
this_is_a_map "yes"

client_script "meta/client.lua"

replace_level_meta 'gta5'

files {
    "gta5.meta",
    "heightmap.dat",
    -- "stream/*.ytyp",
    -- "stream/**/*.ytyp",
    "interiorproxies.meta",
}

data_file "WORLD_HEIGHTMAP_FILE" "heightmap.dat"
data_file "INTERIOR_PROXY_ORDER_FILE" "meta/interiorproxies.meta"
data_file 'DLC_ITYP_REQUEST' 'stream/AntiEXPLOD_props/bfly_noexp.ytyp'
-- data_file "DLC_ITYP_REQUEST" "stream/**/**/*.ytyp"
-- data_file "DLC_ITYP_REQUEST" "stream/**/*.ytyp"
-- data_file "DLC_ITYP_REQUEST" "stream/*.ytyp"
data_file "INTERIOR_PROXY_ORDER_FILE" "interiorproxies.meta"