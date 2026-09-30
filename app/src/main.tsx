// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '../../web/src/styles/palette.css'; // the one palette the site and the app share (U3)
import './styles/base.css';
import './styles/app.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
