import { NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Tasks from './pages/Tasks'
import Notes from './pages/Notes'
import NoteDetail from './pages/NoteDetail'
import Collections from './pages/Collections'
import Quiz from './pages/Quiz'
import WrongAnswers from './pages/WrongAnswers'
import Review from './pages/Review'
import Settings from './pages/Settings'

const NAV = [
  { to: '/', glyph: '▣', label: '工作台', end: true },
  { to: '/tasks', glyph: '⏱', label: '任务' },
  { to: '/notes', glyph: '✎', label: '笔记' },
  { to: '/collections', glyph: '▤', label: '合集' },
  { to: '/quiz', glyph: '✓', label: '自测' },
  { to: '/wrong', glyph: '⚑', label: '错题' },
  { to: '/review', glyph: '❏', label: '复习' },
  { to: '/settings', glyph: '⚙', label: '设置' },
]

const TITLES: Record<string, string> = {
  '/': '工作台',
  '/tasks': '任务面板',
  '/notes': '笔记库',
  '/collections': '合集与课程',
  '/quiz': '自测练习',
  '/wrong': '错题本',
  '/review': '复习资料',
  '/settings': '设置',
}

export default function App() {
  const location = useLocation()
  const title =
    TITLES[location.pathname] ||
    (location.pathname.startsWith('/notes/') ? '笔记' : 'BiliNote')

  return (
    <div className="app">
      <nav className="rail">
        <div className="rail-mark">BN·8483</div>
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => (isActive ? 'rail-item active' : 'rail-item')}
          >
            <span className="glyph">{item.glyph}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <main className="main">
        <div className="topbar">
          <h1>{title}</h1>
          <span className="meta">BiliNote · 视频变结构化笔记</span>
        </div>

        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/notes" element={<Notes />} />
          <Route path="/notes/:taskId" element={<NoteDetail />} />
          <Route path="/collections" element={<Collections />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/wrong" element={<WrongAnswers />} />
          <Route path="/review" element={<Review />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  )
}
