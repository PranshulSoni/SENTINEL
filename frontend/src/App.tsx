import React from 'react';
import AppShell from './components/layout/AppShell';
import Sidebar from './components/outputs/Sidebar';
import TrafficMap from './components/map/TrafficMap';
import ChatPanel from './components/layout/ChatPanel';

const App: React.FC = () => {
  return (
    <AppShell
      leftPanel={<Sidebar />}
      centerPanel={<TrafficMap />}
      rightPanel={<ChatPanel />}
    />
  );
};

export default App;
