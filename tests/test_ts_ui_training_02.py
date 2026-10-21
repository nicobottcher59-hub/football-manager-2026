"""TS-UI-03.02: pictured Training banner, shared portraits, independent training layers."""
from pathlib import Path

from football_manager.domain.club_support import TrainingPolicy
from football_manager.domain.player_development import FOCUSES
from football_manager.services.club_support import effective_intensity
from football_manager.ui_shell.static_assets import find_frontend_root, resolve_static_asset


def test_training_banner_photo_is_served_by_real_static_resolver():
    frontend = find_frontend_root()
    photo = resolve_static_asset('/portable/assets/training/training-session-dusk.jpg', frontend)
    assert photo is not None and photo.is_file()
    assert photo.read_bytes().startswith(b'\xff\xd8\xff')
    stylesheet = (frontend / 'portable/club_support.css').read_text()
    assert "url('assets/training/training-session-dusk.jpg')" in stylesheet
    assert "url('assets/stadium.svg') center 44%" not in stylesheet


def test_training_and_squad_share_photo_manifest_and_player_ids():
    frontend = find_frontend_root()
    catalogue = resolve_static_asset('/public/squad/data/player-portraits.json', frontend)
    assert catalogue is not None and catalogue.is_file()
    squad_js = (frontend / 'public/squad/squad_ui02.js').read_text()
    training_js = (frontend / 'portable/club_support.js').read_text()
    assert "fetch('data/player-portraits.json'" in squad_js
    assert "fetch('/public/squad/data/player-portraits.json'" in training_js
    assert 'trainingPhotoSources.get(String(player.id))' in training_js
    assert 'src="/public/squad/${esc(photo)}"' in training_js
    assert 'window.FMPortraits?.portrait?.(player' in training_js
    assert 'window.FMPortraits?.portrait(player' in squad_js


def test_unified_automatic_workload_and_individual_development_focus_are_separate():
    policy=TrainingPolicy()
    assert effective_intensity(policy,90,15,None,sharpness=70)=='balanced'
    policy.individual_intensities['player-1']='intense'
    assert effective_intensity(policy,90,15,None,player_id='player-1',sharpness=70)=='intense'
    assert effective_intensity(policy,90,15,None,player_id='player-2',sharpness=70)=='balanced'
    # A development focus is independent of daily workout intensity.
    assert 'physical' in FOCUSES and 'intense' not in FOCUSES
    assert 'goalkeeping' not in FOCUSES


def test_photo_layer_does_not_change_backend_or_save_model():
    # A shared photograph is a presentation resource only.
    root = Path(__file__).resolve().parents[1]
    script = (root / 'frontend/portable/club_support.js').read_text()
    assert 'function trainingPortrait(player)' in script
    assert "image.addEventListener('error',()=>image.remove(),{once:true})" in script
    assert 'if(validSquadPhoto(path))trainingPhotoSources.set(id,path)' in script
    assert "if(route==='training')ensureTrainingPhotos();refresh();" in script
