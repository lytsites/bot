import React from 'react'
import Sidebar from '../components/Sidebar'
import HomeListening from '../sideTabs/HomeListening'
import HomeAutoChat from '../sideTabs/HomeAutoChat'
import HomeAutoChatHistory from '../sideTabs/HomeAutoChatHistory'
import HomeRequisitesHistory from '../sideTabs/HomeRequisitesHistory'

export default function HomeTab({
  activeSideTab,
  setActiveSideTab,
  listeningProps,
  autoChatProps,
  autoChatHistoryProps,
  requisitesHistoryProps,
}) {
  const items = [
    { id: 'listening', label: 'Прослушивание' },
    { id: 'auto', label: 'Авто. общение' },
    { id: 'auto_history', label: 'История диалогов' },
    { id: 'requisites_history', label: 'История реквизитов' },
  ]

  return (
    <div className="workspace">
      <Sidebar title="Главная" items={items} activeId={activeSideTab} onChange={setActiveSideTab} />
      <div className="workspace-main">
        {activeSideTab === 'listening' && <HomeListening {...listeningProps} />}
        {activeSideTab === 'auto' && <HomeAutoChat {...autoChatProps} />}
        {activeSideTab === 'auto_history' && <HomeAutoChatHistory {...autoChatHistoryProps} />}
        {activeSideTab === 'requisites_history' && <HomeRequisitesHistory {...requisitesHistoryProps} />}
      </div>
    </div>
  )
}
