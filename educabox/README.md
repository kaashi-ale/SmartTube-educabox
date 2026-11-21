# SmartTube para Educabox Linux

Este diretório contém a primeira adaptação para o Educabox ARMv7. A interface GTK porta parte da navegação do SmartTube. O instalador lê as definições de seção diretamente de BrowsePresenter.java e usa os ícones e as traduções pt-BR do código Android. A interface Linux mostra abas laterais e capas carregadas sob demanda. Em alta, Músicas, Jogos e Esportes executam buscas temáticas. Início e Histórico mostram os vídeos abertos na conta local do Educabox. Busca e resolução de links usam yt-dlp. O GStreamer usa o decodificador Rockchip MPP e a saída rkximagesink.

No Educabox já preparado com GTK 3 (Python GI), XFCE, FFmpeg, GStreamer 1.14 com os plugins Rockchip em ~/.local/opt/rk-media, yt-dlp ARMv7 em ~/.local/opt/edu-yt-dlp e o ambiente NVM usado pelo reprodutor Educabox, execute da raiz:

```sh
bash educabox/install.sh
```

Abra **SmartTube Educabox** na área de trabalho. Pesquise ou cole um link e use as setas e Enter. O histórico fica na conta local. F11 alterna tela cheia e Ctrl+L volta para a busca. O menu oferece 720p (até 30 fps no formato preferido) e 360p. O aplicativo Android e o reprodutor ExoPlayer continuam na árvore upstream. A adaptação Linux ainda depende da preparação específica do sistema e não inclui autenticação, inscrições ou SponsorBlock.
