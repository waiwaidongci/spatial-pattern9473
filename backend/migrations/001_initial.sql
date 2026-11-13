-- Initial schema bootstraps via SQLAlchemy metadata. Optional upgrade indexes:
CREATE INDEX cell_survey_position_idx ON grid_cells (survey_id,row,col);
CREATE INDEX note_run_status_idx ON sampling_notes (run_id,status);
