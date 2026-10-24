import React, { useState, useEffect, useCallback } from 'react';
import LeftPanel from './LeftPanel';
import DocumentViewer3D from './DocumentViewer3D';
import RiskPanel from './RiskPanel';
import {
  getDocuments,
  getDocument,
  analyzeContract,
  deleteDocument,
  searchDocument,
} from '../api/client';
import '../styles/document-dashboard.css';

/**
 * DocumentDashboard: Main orchestrator for the 3D Interactive Document Risk Analysis Dashboard
 * Combines LeftPanel (upload/history), DocumentViewer3D (center 3D paper stage),
 * and RiskPanel (right risks sidebar).
 */
export default function DocumentDashboard({ onBackToHome }) {
  const [documents, setDocuments] = useState([]);
  const [activeDocId, setActiveDocId] = useState(null);
  const [documentData, setDocumentData] = useState(null);
  const [activeClauseId, setActiveClauseId] = useState(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  // Load document list on startup
  const fetchDocList = useCallback(async () => {
    try {
      const res = await getDocuments();
      const docs = res.documents || [];
      setDocuments(docs);
      // Auto-select latest document if none selected
      if (docs.length > 0 && !activeDocId) {
        loadDoc(docs[0].id);
      }
    } catch (err) {
      console.error('Failed to load documents list:', err);
    }
  }, [activeDocId]);

  useEffect(() => {
    fetchDocList();
  }, []);

  // Load specific document data
  const loadDoc = async (docId) => {
    try {
      setActiveDocId(docId);
      setActiveClauseId(null);
      setSearchResults([]);
      setSearchQuery('');
      const data = await getDocument(docId);
      setDocumentData(data);
    } catch (err) {
      console.error(`Failed to load document ${docId}:`, err);
    }
  };

  // Upload handler
  const handleUpload = async (file) => {
    setIsUploading(true);
    setUploadError(null);
    try {
      const result = await analyzeContract(file);
      setDocumentData(result);
      setActiveDocId(result.document_id);
      setActiveClauseId(null);
      setSearchResults([]);
      // Refresh documents list
      await fetchDocList();
    } catch (err) {
      console.error('Upload & analysis error:', err);
      setUploadError(err.message || 'Failed to analyze contract.');
    } finally {
      setIsUploading(false);
    }
  };

  // Delete handler
  const handleDeleteDoc = async (docId) => {
    try {
      await deleteDocument(docId);
      const updated = documents.filter((d) => d.id !== docId);
      setDocuments(updated);
      if (activeDocId === docId) {
        if (updated.length > 0) {
          loadDoc(updated[0].id);
        } else {
          setActiveDocId(null);
          setDocumentData(null);
          setActiveClauseId(null);
        }
      }
    } catch (err) {
      console.error('Failed to delete document:', err);
      alert('Failed to delete document.');
    }
  };

  // Semantic Search
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (!query || !activeDocId) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const res = await searchDocument(activeDocId, query, 5);
      setSearchResults(res.results || []);
      // If there are results, jump to top match
      if (res.results && res.results.length > 0) {
        setActiveClauseId(res.results[0].clause_id);
      }
    } catch (err) {
      console.error('Semantic search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  // Select clause handler
  const handleSelectClause = (clauseId) => {
    setActiveClauseId(clauseId);
  };

  return (
    <div className="dd-app">
      {/* Top App Header */}
      <header className="dd-header">
        <div className="dd-header-left">
          <div className="dd-brand-badge">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>CLAUSEGUARD 3D</span>
          </div>

          {documentData && (
            <div className="dd-doc-tab">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span className="dd-doc-tab-title" title={documentData.filename}>
                {documentData.filename}
              </span>
            </div>
          )}
        </div>

        <div className="dd-header-actions">
          {onBackToHome && (
            <button
              className="dd-header-btn"
              onClick={onBackToHome}
              title="Return to Front Page"
            >
              ← Home
            </button>
          )}
          <button
            className={`dd-header-btn ${leftCollapsed ? 'active' : ''}`}
            onClick={() => setLeftCollapsed(!leftCollapsed)}
            title="Toggle Documents sidebar"
          >
            📁 Documents
          </button>
          <button
            className={`dd-header-btn ${rightCollapsed ? 'active' : ''}`}
            onClick={() => setRightCollapsed(!rightCollapsed)}
            title="Toggle Risks sidebar"
          >
            ⚠️ Risks Panel
          </button>
        </div>
      </header>

      {/* 3-Column Split Cockpit */}
      <div className="dd-body dd-workspace">
        {/* Left Panel: Upload Drop Box & Document History */}
        <LeftPanel
          documents={documents}
          activeDocId={activeDocId}
          onSelectDoc={loadDoc}
          onUpload={handleUpload}
          onDeleteDoc={handleDeleteDoc}
          isUploading={isUploading}
          uploadError={uploadError}
          isCollapsed={leftCollapsed}
          onToggleCollapse={() => setLeftCollapsed(!leftCollapsed)}
        />

        {/* Center: 3D Document Paper Stage & Inline Highlights */}
        <DocumentViewer3D
          documentData={documentData}
          activeClauseId={activeClauseId}
          onSelectClause={handleSelectClause}
          searchQuery={searchQuery}
          onSearch={handleSearch}
          searchResults={searchResults}
          isSearching={isSearching}
        />

        {/* Right Panel: Risks Findings & Recommendations Accordion */}
        <RiskPanel
          clauses={documentData?.clauses || []}
          activeClauseId={activeClauseId}
          onSelectClause={handleSelectClause}
          isCollapsed={rightCollapsed}
          onToggleCollapse={() => setRightCollapsed(!rightCollapsed)}
        />
      </div>
    </div>
  );
}
