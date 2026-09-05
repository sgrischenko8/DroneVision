# резолвер: пердбачає пріоритетність протоколів дій незалежних модулів (fire.py, thermal.py,
# power_save.py) 
#
# дві незалежні політики:
# 1. resolve_reading() - thermal vs FIRE: поки йде захват цілі, дії по перегріву відкладаються
# 2. resolve_fire_activation()/resolve_fire_frame() - fire vs power_save: FIRE головніше.
#    поки триває захват, power save завжди вимкнений навіть якщо оператор увімкнув його
#    вручну. При TARGET_LOST вмикається назад, тільки якщо це і так було б виправдано
#    (низький заряд або було увімкнено вручну ДО захвату)

from thermal import ThermalDecision

def resolve_reading(thermal, temp_c, frame, frame_idx, video_time, fire):
    decision = thermal.evaluate(temp_c, frame, frame_idx, video_time, rth_active=False)

    fire_active = fire.locked_id is not None
    if fire_active and decision.action != ThermalDecision.NONE:
        print(f"[thermal-resolver] {decision.level} під час FIRE - дію відкладено")
        return decision

    thermal.commit(decision, video_time)
    return decision

def resolve_fire_activation(fire, power_save, tracked_objects, frame, frame_idx, video_time):
    was_locked_before = fire.locked_id is not None
    fire.activate(tracked_objects, frame=frame, frame_idx=frame_idx, video_time=video_time)

    just_locked = (not was_locked_before) and (fire.locked_id is not None)
    if not just_locked:
        return

    fire.pre_fire_power_save_enabled = power_save.enabled
    if power_save.enabled:
        power_save.toggle(frame, frame_idx, video_time)

def resolve_fire_frame(fire, power_save, tracked_objects, frame, frame_idx, video_time, battery_low):
    was_locked_before = fire.locked_id is not None
    is_locked_now = fire.process_frame(frame, tracked_objects, frame_idx, video_time)

    just_lost = was_locked_before and not is_locked_now
    if just_lost:
        should_restore = battery_low or bool(fire.pre_fire_power_save_enabled)
        fire.pre_fire_power_save_enabled = None
        if should_restore and not power_save.enabled:
            power_save.toggle(frame, frame_idx, video_time)

    return is_locked_now