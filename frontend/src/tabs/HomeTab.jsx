import React from 'react'
import Sidebar from '../components/Sidebar'
import HomeListening from '../sideTabs/HomeListening'
import HomeAutoChat from '../sideTabs/HomeAutoChat'

export default function HomeTab({
  activeSideTab,
  setActiveSideTab,
  listeningProps,
  autoChatProps,
  canGroupReading = true,
  canAutoDialogs = true,
}) {
  const items = []
  if (canGroupReading) items.push({ id: 'listening', label: 'Чтение групп' })
  if (canAutoDialogs) items.push({ id: 'auto', label: 'Авто. диалоги' })

  return (
    <div className="workspace">
      <Sidebar title="Главная" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'listening' && canGroupReading && <HomeListening {...listeningProps} />}
        {activeSideTab === 'auto' && canAutoDialogs && <HomeAutoChat {...autoChatProps} />}
      </div>
    </div>
  )
}
