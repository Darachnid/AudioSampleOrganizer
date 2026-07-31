cmake_minimum_required(VERSION 3.21)
project(ClipMark VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Multimedia)
find_package(PkgConfig REQUIRED)
pkg_check_modules(SNDFILE REQUIRED IMPORTED_TARGET sndfile)

add_executable(ClipMark
    src/main.cpp
    src/MainWindow.cpp
    src/MainWindow.h
    src/AudioEngine.cpp
    src/AudioEngine.h
    src/ClipModel.cpp
    src/ClipModel.h
    src/MetadataStore.cpp
    src/MetadataStore.h
    src/ClipExporter.cpp
    src/ClipExporter.h
    src/StatusDialog.cpp
    src/StatusDialog.h
    src/AppMode.h
)

target_include_directories(ClipMark PRIVATE src)

target_link_libraries(ClipMark PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Multimedia
    PkgConfig::SNDFILE
)

install(TARGETS ClipMark RUNTIME DESTINATION bin)
