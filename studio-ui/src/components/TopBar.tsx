import { FilePlus, Save, Zap, Undo2, Redo2, RotateCcw, Sun, Moon, HelpCircle, Clock } from 'lucide-react';
import type { ProjectSummary, Project } from '../lib/api';
import { Button, Badge, fmt } from './ui';

// Top bar: project selection / new / rename / save / quick save, duration pill,
// theme toggle, shortcuts help, revision + unsaved + stale state.
// All names are rendered as text (React escapes) — no HTML injection from names/paths.

export function TopBar(props: {
  projects: ProjectSummary[];
  project: Project | null;
  dirty: boolean;
  stale: boolean;
  busy: boolean;
  totalDuration: number;
  clipCount: number;
  theme: 'dark' | 'light';
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (name: string) => void;
  onSave: () => void;
  onQuickSave: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onReload: () => void;
  onToggleTheme: () => void;
  onToggleShortcuts: () => void;
}) {
  const { project } = props;
  return (
    <div className="topbar">
      <span className="brand">
        <FilePlus size={16} /> Studio
      </span>

      <select
        className="select topbar-select"
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
          className="input topbar-name"
          value={project.name}
          onChange={(e) => props.onRename(e.target.value)}
          aria-label="Project name"
        />
      )}

      {project && props.clipCount > 0 && (
        <span className="pill mono" title="Total timeline duration">
          <Clock size={12} /> {fmt(props.totalDuration)}
        </span>
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
            size="sm"
            onClick={props.onQuickSave}
            disabled={!props.dirty || props.busy || props.stale}
            title="Quick save (no prompt)"
          >
            <Zap size={14} /> Quick Save
          </Button>

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

      <div className="topbar-utils">
        <Button
          size="icon"
          className="ghost"
          onClick={props.onToggleTheme}
          title={props.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          aria-label={props.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {props.theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </Button>
        <Button
          size="icon"
          className="ghost"
          onClick={props.onToggleShortcuts}
          title="Keyboard shortcuts (?)"
          aria-label="Keyboard shortcuts"
        >
          <HelpCircle size={16} />
        </Button>
      </div>
    </div>
  );
}
