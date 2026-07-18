import { Route, Routes } from 'react-router-dom';

import Layout from './components/Layout';
import Collections from './pages/Collections';
import Library from './pages/Library';
import MathomDetail from './pages/MathomDetail';
import Templates from './pages/Templates';
import Timeline from './pages/Timeline';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Library />} />
        <Route path="mathoms/:id" element={<MathomDetail />} />
        <Route path="templates" element={<Templates />} />
        <Route path="collections" element={<Collections />} />
        <Route path="timeline" element={<Timeline />} />
      </Route>
    </Routes>
  );
}
