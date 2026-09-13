# BUILD-CLEANUP — Clang warning cleanup plan

Source: uploaded build log `cmake --build build --config Debug --target all --` (360 targets, exit 0, clang warnings).
Workspace root: `/home/mouse/Desktop/idTech4-HellOnWheels/idTech4-dhewm3`
Log paths like `/home/mouse/Documents/GitHub/idTech4-dhewm3/neo/...` map to `<workspace>/neo/...`.

Scope: ONLY workspace code. Dependencies explicitly EXCLUDED:

* `neo/libs/imgui/**` — third-party Dear ImGui, no warnings in log.
* `neo/framework/miniz/**`, `neo/framework/minizip/**`, `neo/renderer/stblib_impls.c`, `neo/renderer/stb_image.h` — third-party, no warnings.
* `neo/sound/stb_vorbis.h:1448` + `neo/sound/stbvorbis_impl.c` — third-party stb, `[-Wtautological-compare]` EXCLUDED, do not touch.
* `/usr/include/curl/curl.h` notes — system header, EXCLUDED.
* `game/AF.cpp:901`, `d3xp/AF.cpp:901` `[-Wenum-compare]` — WONTFIX per user (existing FIXME about DECLAF_CONSTRAINT_* vs CONSTRAINT_* value mismatch is correct).

Global rules:

* Non-destructive only. Where removal is the only option, comment out + add line just before:
  `// BUILD-CLEANUP: <why dead / why safe> - warning [-W...]`
* C++98 compatible (C++11 only if IMGUI on). DO NOT use `[[maybe_unused]]` (C++17).
* `neo/CMakeLists.txt:454-457` already has `-Wno-class-memaccess` for GCC; clang still emits `-Wnontrivial-memcall`, hence `(void*)` casts.
* Verify per phase: `cmake --build build --config Debug 2>&1 | grep -E "warning:"` count must drop, no new warnings, `build/dhewm3` still links.

User decisions applied from guidance:

* `-Wnontrivial-memcall` → cast first arg to `(void*)` as compiler suggests.
* `-Wunused-but-set-*` → keep code, add `(void)var;`.
* `-Wunused-private-field` → keep field for ABI/layout, suppress with pragma.
* `CURLOPT_PROGRESSFUNCTION` → suppress, do not migrate.
* `AF.cpp:901` enum-compare → ignore / WONTFIX.

Edit patterns:

```cpp
// memcall memset:
memset( &renderEntity, 0, sizeof(renderEntity) );
// -> memset( (void*)&renderEntity, 0, sizeof(renderEntity) );

// memcall memcpy, Heap.h:
memcpy( tri->verts, &verts[...], n );
// -> memcpy( (void*)tri->verts, &verts[...], n );
memcpy( block->GetMemory(), oldBlock->GetMemory(), sz );
// -> memcpy( (void*)block->GetMemory(), oldBlock->GetMemory(), sz );

// unused-but-set local/counter, keep increments for debug history:
int c_backfaced;
(void)c_backfaced;

// file-scope unused const/function - (void) invalid, comment out:
// BUILD-CLEANUP: ROQ_QUAD never read, kept as comment for spec reference - [-Wunused-const-variable]
// const int ROQ_QUAD = 0x1000;

// unused private field - keep + suppress (example Model_local.h):
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-private-field"
#endif
int index; // kept for ABI/layout, never read
#ifdef __clang__
#pragma clang diagnostic pop
#endif
```

---

## Phase 0 — Baseline + inventory [no code change]

- [ ] `0.1` Clean rebuild capturing log: `cmake --build build --config Debug 2>&1 | tee /tmp/opencode/build-clean.log`
- [ ] `0.2` Confirm warning set matches this file inventory (~230 warnings, ~150 memcall).
- [ ] `0.3` Confirm `neo/config.h` is generated, not edited.

## Phase 1 — Safe mechanical fixes (low risk, 6 files)

- [ ] `1.1` `neo/idlib/geometry/Winding.cpp:105,253` `[-Wundefined-bool-conversion]` `assert(this && numPoints>0)`:
  Change to `assert(numPoints > 0);` both sites. `this` can never be null in well-defined C++. Non-destructive, behavior identical.
- [ ] `1.2` `neo/sys/posix/posix_main.cpp:773` `[-Wmissing-braces]` `struct sigaction sigact = {0};`:
  Change to `struct sigaction sigact = {};` (or `memset`). Verify Linux build only.
- [ ] `1.3` `neo/renderer/Image_load.cpp:1723` `[-Wself-assign-field]` `timestamp = timestamp;` NEEDS-REVIEW:
  Likely dead no-op. Plan: comment out with `// BUILD-CLEANUP: self-assign no-op...` + `(void)timestamp;` if member must be marked used. Check if `timestamp = <param>` was intended.
- [ ] `1.4` `neo/game/script/Script_Program.cpp:655`, `neo/d3xp/script/Script_Program.cpp:655` `[-Wself-assign-field]` `initialized = initialized;` in `SetObject` NEEDS-REVIEW:
  Compare `SetFunction:643` does `initialized = initializedConstant;`. Likely bug, should be same. Plan: fix to `initialized = initializedConstant;` OR if uncertain comment out + `(void)initialized;`. Flag for owner review, do not guess silently.
- [ ] `1.5` Rebuild, confirm 1.1-1.4 warnings gone.

## Phase 2 — Unused variables / consts / functions

### 2A — `-Wunused-but-set-variable` → add `(void)var;` (keep assignments)

- [ ] `2A.1` `neo/idlib/Lexer.cpp:362` `int c,val,i;` → add `(void)i;` after decl. Check if `i` increment in `ReadEscapeCharacter` hex loop is dead.
- [ ] `2A.2` `neo/idlib/Str.cpp:267` `int i,found,index;` in `Filter` → `(void)i;`.
- [ ] `2A.3` `neo/renderer/Image_process.cpp:349` `float totalSpec;` → `(void)totalSpec;`.
- [ ] `2A.4` `neo/renderer/Image_load.cpp:215` `rgbOr,rgbAnd` → `(void)rgbOr; (void)rgbAnd;` (keep `aOr,aAnd` logic).
- [ ] `2A.5` `neo/renderer/Model.cpp:585` `totalVerts,totalIndexes` → two `(void)` lines.
- [ ] `2A.6` `neo/renderer/Interaction.cpp:289,290` `c_backfaced,c_distance` → `(void)` both.
- [ ] `2A.7` `neo/renderer/RenderWorld.cpp:94,95` `totalRef,totalIntr`; `:1192` `numSurfaces` → `(void)` each.
- [ ] `2A.8` `neo/renderer/VertexCache.cpp:507,508` `frameStatic,totalStatic` → `(void)`.
- [ ] `2A.9` `neo/renderer/tr_font.cpp:314` `glyphScale` → `(void)glyphScale;`.
- [ ] `2A.10` `neo/renderer/tr_orderIndexes.cpp:101` `c_starts` → `(void)`.
- [ ] `2A.11` `neo/renderer/tr_trace.cpp:47` `c_testEdges,c_testPlanes,c_intersect` → three `(void)`.
- [ ] `2A.12` `neo/renderer/tr_subview.cpp:111` `pointOr` → `(void)pointOr;`.
- [ ] `2A.13` `neo/renderer/tr_trisurf.cpp:735` `c_removed,c_unique`; `:1038` `shared`; `:1197` `c_textureDegenerateFaces`; `:1198` `c_positive,c_negative` → `(void)` each, keep debug counting code.
- [ ] `2A.14` `neo/tools/compilers/dmap/facebsp.cpp:190` `front,back` → `(void)front; (void)back;`.
- [ ] `2A.15` `neo/tools/compilers/aas/BrushBSP.cpp:1361` `count` in `int count,next,s;` → `(void)count;`.
- [ ] `2A.16` `neo/tools/compilers/roqvq/roqParam.cpp:44` `readarg` → `(void)readarg;`.
- [ ] `2A.17` `neo/tools/compilers/renderbump/renderbump.cpp:525` `c_hits` → `(void)c_hits;`.
- [ ] `2A.18` `neo/sound/snd_system.cpp:170` `totalPCMMemory` → `(void)totalPCMMemory;`.
- [ ] `2A.19` `neo/game/Game_local.cpp:2370` `int c=0;`; `neo/d3xp/Game_local.cpp:2624` same + `:2441` `int num=0;` → `(void)c; (void)num;`.
- [ ] `2A.20` `neo/game/physics/Physics_AF.cpp:3958`, `neo/d3xp/physics/Physics_AF.cpp:3959` `float velocity,...` → `(void)velocity;`.

### 2B — `-Wunused-but-set-global` → keep decl, `(void)` at use site or comment increments

- [ ] `2B.1` `neo/renderer/Model_md5.cpp:43,44,45` `c_numVerts,c_numWeights,c_numWeightJoints` → add `(void)` reads where incremented, do not delete decl.
- [ ] `2B.2` `neo/tools/compilers/dmap/tritjunction.cpp:99` `numHashVerts,numTotalVerts` → same.
- [ ] `2B.3` `neo/tools/compilers/renderbump/renderbump.cpp:108` `oldWidth,oldHeight` → same.

### 2C — `-Wunused-const-variable` file-scope → comment out + explanation (no `(void)` possible)

- [ ] `2C.1` `neo/renderer/Cinematic.cpp:128` `ROQ_QUAD` → comment out + `// BUILD-CLEANUP: unused ROQ chunk id...`.
- [ ] `2C.2` `neo/framework/UsercmdGen.cpp:311` `MAX_CHAT_BUFFER` → comment out + note.
- [ ] `2C.3` `neo/framework/Session.cpp:70-73` `PREVIEW_X,Y,WIDTH,HEIGHT` → comment out block + note.
- [ ] `2C.4` `neo/game/physics/Physics_AF.cpp:59`, `neo/d3xp/physics/Physics_AF.cpp:59` `SUSPEND_ANGULAR_ACCELERATION` → comment out + note.

### 2D — `-Wunused-function` → comment out entire function + explanation

- [ ] `2D.1` `neo/idlib/Lib.cpp:368` `RevBitFieldSwap`, `:406` `SixtetsForIntBig`, `:436` `IntForSixtetsBig` → comment out each `ID_INLINE static` body + `// BUILD-CLEANUP: unused, Big-endian helper...`.
- [ ] `2D.2` `neo/renderer/tr_trisurf.cpp:1487` `VectorNormalizeFast2` → comment out + note.

## Phase 3 — `-Wnontrivial-memcall` bulk → `(void*)` first arg (user choice)

Do headers first (high fan-out), then per-subsystem. Example: `memset(&x,0,sizeof(x))` → `memset((void*)&x,0,sizeof(x))`.

- [ ] `3.0` Headers (fix once, benefits game+d3xp+renderer):
  - `neo/idlib/Heap.h:802` `memcpy(block->GetMemory(),...)` → `(void*)block->GetMemory()`.
  - `neo/idlib/math/Extrapolate.h:91,92,93` three `memset(&startValue/&baseSpeed/&speed,...)` → `(void*)` each (instantiated for `idVec3,idAngles`).
  - `neo/idlib/math/Interpolate.h:174` `memset(&startValue,...)` → `(void*)`.
- [ ] `3.1` renderer core:
  - `GuiModel.cpp:181,455,657` `memcpy` `idDrawVert`; `:192` `memset renderEntity_t`.
  - `Material.cpp:2620` `viewDef_t`; `ModelDecal.cpp:50`, `Model_md3.cpp:48,461` `srfTriangles_t`; `Model.cpp:1542` `aseFace_t`.
  - `Model_ase.cpp:693,764,797`; `Model_ma.cpp:150`; `RenderEntity.cpp:34,80`; `RenderSystem_init.cpp:2328`; `RenderWorld.cpp:1389`; `tr_deform.cpp:200,917`; `tr_trisurf.cpp:421,525,544,2084,2206`.
- [ ] `3.2` framework/cm/dmap/aas:
  - `framework/DeclParticle.cpp:94,98`; `framework/Common.cpp:1267` `MemInfo_t`; `framework/async/AsyncServer.cpp:1865` `challenge_t`.
  - `cm/CollisionModel_load.cpp:1455,2416,2497,3022,3030,3328`; `cm/CollisionModel_rotate.cpp:1622`; `cm/CollisionModel_translate.cpp:784`.
  - `tools/compilers/dmap/optimize.cpp:215,364`; `map.cpp:409,541`; `tritjunction.cpp:633`; `ubrush.cpp:84,144,475,491,609`; `tritools.cpp:48,323`; `usurface.cpp:85,664`; `tools/compilers/aas/AASBuild_file.cpp:483`; `tools/compilers/renderbump/renderbump.cpp:319,894`.
  - `ui/RenderWindow.cpp:100,147`.
- [ ] `3.3` game/ (mirror in d3xp/ with same pattern, d3xp line numbers in parens):
  - `AFEntity.cpp:2276,2346,2752,2823,2825` (d3xp:2555,2625,3031,3102,3104); `Fx.cpp:121,130,171,416,502` (same d3xp); `Entity.cpp:235,326,433,435,1503,3611` (d3xp:251,342,449,451,456,1595,3716 +456 xrayEntity); `Light.cpp:88,196` (same); `Moveable.cpp:752,753,840,841,897,931` (d3xp:843,844,941,942,1030,1049,1086); `Mover.cpp:142,143` (d3xp:144,145); `PlayerIcon.cpp:146` (d3xp:162); `Pvs.cpp:135` (same); `PlayerView.cpp:47` (d3xp:58); `Player.cpp:7334,8018` (d3xp:8711,9545 +2526 WeaponToggle_t); `Projectile.cpp:87,228,697,984,1016,1142,1205,1688,1714,1895,1935` (d3xp:99,249,738,1077,1115,1310,1373,1871,1897,2103,2143,2182); `SmokeParticles.cpp:44,72` (d3xp:45,73); `Weapon.cpp:141,142,143,144,597,617,841,907,1620` (d3xp:165,166,167,168,656,721,741,993,1068,1253,1890); `ai/AI_pathing.cpp:1052` (d3xp:1049); `ai/AI.cpp:340,951` (d3xp:343,1029); `anim/Anim_Blend.cpp:4983` (d3xp:5069); `script/Script_Thread.cpp:530` (d3xp:552); `physics/Clip.cpp:973,1080,1149,1241,1301` (d3xp:979,1084,1153,1245,1305); `physics/Physics_Base.cpp:251,448,457` (same); `physics/Physics_Parametric.cpp:124` (same); `physics/Physics_Monster.cpp:253` (same); `physics/Push.cpp:731,885,1060,1241,1402` (same); `physics/Physics_Player.cpp:941,1502,1517` (same); `physics/Physics_Static.cpp:293,652` (same); `physics/Physics_AF.cpp:3912,7399,7481` (d3xp:3913,7400,7482); `physics/Physics_RigidBody.cpp:447` (same); `physics/Physics_StaticMulti.cpp:405,724,734,845` (same).
- [ ] `3.4` Rebuild, confirm memcall count → 0 for workspace files.

## Phase 4 — Semantic / pragma fixes

- [ ] `4.1` `neo/framework/CmdSystem.cpp:727` `[-Wvarargs]` `va_start(argPtr, stripFolder)` with `bool stripFolder:688` NEEDS-REVIEW:
  Options: (a) change signature to `int stripFolder` + update callers, (b) introduce `int stripFolderInt = stripFolder; va_start(argPtr, stripFolderInt)` — but `va_start` must use last named param, so (b) invalid. Plan: change param type to `int`, keep bool semantics, update all call sites. Verify with grep `ArgCompletion_FolderExtension`.
- [ ] `4.2` `neo/framework/FileSystem.cpp:3515` `[-Wdeprecated-declarations]` `CURLOPT_PROGRESSFUNCTION` → suppress per user:
  Wrap `:3508-3528` block with `#pragma GCC diagnostic push/ignored "-Wdeprecated-declarations"` + `// BUILD-CLEANUP: keep legacy progress API...` (also clang `#pragma clang diagnostic`).
- [ ] `4.3` `neo/sys/posix/posix_main.cpp` already done in 1.2.
- [ ] `4.4` `-Wunused-private-field` keep+suppress (12 sites):
  - `renderer/Model_local.h:230 index, :233 numLods`; `framework/UsercmdGen.cpp:405 heldJump`; `ui/EditWindow.h:84 textIndex`; `ui/SliderWindow.h:78 lastValue`; `ui/RenderWindow.h:63 worldModelDef`; `game/Misc.h:571`, `d3xp/Misc.h:580` `model`; `game/gamesys/Event.h:67`, `d3xp/gamesys/Event.h:67` `next`; `tools/compilers/aas/AASReach.h:52,53`; `tools/compilers/roqvq/codec.h:91 index2`; `game/physics/Push.h:91,92`, `d3xp/physics/Push.h:91,92` `pushedGroup, pushedGroupSize`.
  Plan per header: push/ignore/pop `-Wunused-private-field` + `// BUILD-CLEANUP: kept for ABI/serialization...`.

## Phase 5 — Verification

- [ ] `5.1` Full `cmake --build build --config Debug` → 0 workspace warnings (only stb/curl system notes allowed).
- [ ] `5.2` `git diff --stat`, ensure no `neo/libs/imgui`, `miniz*`, `stb*` touched.
- [ ] `5.3` Smoke: `./build/dhewm3 +set fs_basepath ./assets +set r_fullscreen 0 +quit` still reaches prior blocker (`script/doom_main.script`), no new crash.
