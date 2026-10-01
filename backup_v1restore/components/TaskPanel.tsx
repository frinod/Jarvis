'use client'

import { useJarvisStore } from '@/store/jarvisStore'
import { CheckCircle, Loader2, Circle, ListTodo } from 'lucide-react'

export function TaskPanel() {
  const { tasks } = useJarvisStore()

  return (
    <div className="glass rounded-xl p-4">
      <h3 className="text-[11px] text-jarvis-accent uppercase tracking-wider font-semibold mb-3 flex items-center gap-2">
        <ListTodo size={12} />
        Tasks
      </h3>
      {tasks.length === 0 ? (
        <p className="text-jarvis-muted text-[10px]">No active tasks</p>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-center gap-2">
              {task.status === 'completed' ? (
                <CheckCircle size={12} className="text-jarvis-neon-green" />
              ) : task.status === 'running' ? (
                <Loader2 size={12} className="text-jarvis-neon-orange animate-spin" />
              ) : (
                <Circle size={12} className="text-jarvis-muted" />
              )}
              <span className="text-[11px] text-jarvis-text truncate">{task.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
