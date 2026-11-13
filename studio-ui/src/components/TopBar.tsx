import { FilePlus, Save, Undo2, Redo2, RotateCcw } from 'lucide-react';
import type { ProjectSummary, Project } from '../lib/api';
import { Button, Badge } from './ui';

// Top bar: project selection / new / rename / save, revision + unsaved + stale state.
// All names are rendered as text (React escapes) — no HTML injection from names/paths.

export function TopBar(props: {
  projects: ProjectSummary[];
  project: Project | null;
  dirty: boolean;
  stale: boolean;
  busy: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (name: string) => void;
  onSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onReload: () => void;
}) {
  const { project } = props;
  return (
    <div className="topbar">
      <span className="brand">
        <FilePlus size={16} /> Studio
      </span>

      <select
        className="select"
        style={{ width: 200 }}
        value={project?.id || ''}
        onChange={(e) => props.onSelect(e.target.value)}
        aria-label="Select project"
      >
        <option value="" disabled>
          {props.projects.length ? 'Select project…' : 'No projects yet'}
        </option>
        {props.projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} (r{p.revision})
          </option>
        ))}
      </select>

      <Button size="sm" onClick={props.onNew} disabled={props.busy} title="New project">
        <FilePlus size={14} /> New
      </Button>

      {project && (
        <input
          className="input"
          style={{ width: 180 }}
          value={project.name}
          onChange={(e) => props.onRename(e.target.value)}
          aria-label="Project name"
        />
      )}

      <div className="spacer" />

      {project && (
        <>
          <Button
            size="icon"
            className="ghost"
            onClick={props.onUndo}
            disabled={!project.can_undo || props.busy}
            title="Undo (Ctrl+Z)"
          >
            <Undo2 size={16} />
          </Button>
          <Button
            size="icon"
            className="ghost"
            onClick={props.onRedo}
            disabled={!project.can_redo || props.busy}
            title="Redo (Ctrl+Shift+Z)"
          >
            <Redo2 size={16} />
          </Button>

          {props.stale ? (
            <Badge kind="stale">stale — reload</Badge>
          ) : props.dirty ? (
            <Badge kind="dirty">unsaved</Badge>
          ) : (
            <Badge kind="ok">r{project.revision} saved</Badge>
          )}

          {props.stale && (
            <Button size="sm" onClick={props.onReload} title="Reload latest">
              <RotateCcw size={14} /> Reload
            </Button>
          )}

          <Button
            variant="primary"
            size="sm"
            onClick={props.onSave}
            disabled={!props.dirty || props.busy || props.stale}
            title="Save revision (Ctrl+S)"
          >
            <Save size={14} /> Save
          </Button>
        </>
      )}
    </div>
  );
}
