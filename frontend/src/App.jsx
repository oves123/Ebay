import React, { useState, useEffect, useRef } from 'react';
import { Search, Download, ExternalLink, Copy, CheckCircle2, Clock, Activity, Trash2 } from 'lucide-react';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

function App() {
  const [activeTab, setActiveTab] = useState('live'); // 'live' or 'sweep'
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [filters, setFilters] = useState({
    mens: false,
    womens: false,
    bidding: false,
    buyItNow: false,
    acceptsOffers: false,
    belowScrap: false
  });
  const [hiddenItems, setHiddenItems] = useState(() => {
    const saved = localStorage.getItem('hiddenEbayItems');
    return saved ? JSON.parse(saved) : [];
  });
  const itemsPerPage = 100;

  const [isAutoPolling, setIsAutoPolling] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const soundEnabledRef = useRef(false);
  const lastLatestLinkRef = useRef(null);

  useEffect(() => {
    fetchData(activeTab);
    setCurrentPage(1); // Reset page on tab change
    
    // Auto polling for Live Sniper
    let interval;
    if (activeTab === 'live' && isAutoPolling) {
      interval = setInterval(() => {
        fetchData('live', true);
      }, 5000);
    }
    return () => clearInterval(interval);
  }, [activeTab, isAutoPolling]);

  const fetchData = async (tab, isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const endpoint = tab === 'live' ? '/live' : '/sweep';
      const response = await fetch(`${API_BASE_URL}${endpoint}`);
      const json = await response.json();
      const newData = json.data || [];
      
      // Check for new snipes if we're silently polling the live tab
      if (isSilent && tab === 'live' && newData.length > 0) {
        const currentLatestLink = newData[0].Link;
        
        // If this is the first silent load, just set the link
        if (!lastLatestLinkRef.current) {
          lastLatestLinkRef.current = currentLatestLink;
        } else if (currentLatestLink !== lastLatestLinkRef.current) {
          // A new snipe has arrived!
          lastLatestLinkRef.current = currentLatestLink;
          if (soundEnabledRef.current) {
            playDing();
          }
        }
      } else if (!isSilent && tab === 'live' && newData.length > 0) {
          lastLatestLinkRef.current = newData[0].Link;
      }
      
      setData(newData);
    } catch (error) {
      console.error('Error fetching data:', error);
      if (!isSilent) setData([]);
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  const playDing = () => {
    try {
      const audio = new Audio('https://www.myinstants.com/media/sounds/ding-sound-effect_2.mp3');
      audio.volume = 0.5;
      audio.play().catch(e => console.log('Audio play failed (user needs to interact first)', e));
    } catch (err) { }
  };

  const toggleSound = () => {
    const newState = !soundEnabled;
    setSoundEnabled(newState);
    soundEnabledRef.current = newState;
    if (newState) {
      // Play a silent sound immediately on click to unlock the browser's audio context for mobile!
      const audio = new Audio('https://www.myinstants.com/media/sounds/ding-sound-effect_2.mp3');
      audio.volume = 0.01;
      audio.play().catch(e => {});
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // Could add a toast notification here
  };

  const downloadCSV = () => {
    if (data.length === 0) return;
    
    // Create CSV header
    const headers = Object.keys(data[0]);
    const csvContent = [
      headers.join(','),
      ...data.map(row => 
        headers.map(header => {
          let cell = row[header] === null ? '' : String(row[header]);
          // Escape quotes and wrap in quotes if there are commas
          if (cell.includes(',') || cell.includes('"')) {
            cell = `"${cell.replace(/"/g, '""')}"`;
          }
          return cell;
        }).join(',')
      )
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `ebay_arbitrage_${activeTab}_${new Date().toISOString().slice(0,10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const toggleFilter = (key) => {
    setFilters(prev => ({ ...prev, [key]: !prev[key] }));
    setCurrentPage(1);
  };

  const hideItem = (link) => {
    const newHidden = [...hiddenItems, link];
    setHiddenItems(newHidden);
    localStorage.setItem('hiddenEbayItems', JSON.stringify(newHidden));
  };

  const filteredData = data.filter(item => {
    // Hidden Items
    if (hiddenItems.includes(item.Link)) return false;

    // Dropdown Category Search
    if (selectedCategory !== 'All' && item.Query !== selectedCategory) return false;

    // Text search
    const matchesSearch = item.Title?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          item.Query?.toLowerCase().includes(searchTerm.toLowerCase());
                          
    if (!matchesSearch) return false;
    
    // Chips filters
    if (filters.mens && item.Gender !== 'Mens') return false;
    if (filters.womens && item.Gender !== 'Womens') return false;
    if (filters.bidding && !item.BuyingOptions?.includes('Bidding')) return false;
    if (filters.buyItNow && !item.BuyingOptions?.includes('Buy It Now')) return false;
    if (filters.acceptsOffers && !item.BuyingOptions?.includes('Accepts Offers')) return false;
    if (filters.belowScrap) {
      if (!item.ScrapValue || item.ScrapValue === 'N/A') return false;
      const scrap = parseInt(item.ScrapValue.replace('$', ''));
      if (item.Price >= scrap) return false;
    }
    
    return true;
  });

  // Pagination logic
  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const currentData = filteredData.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  return (
    <div className="dashboard-container">
      <header className="header">
        <div className="header-title">
          <Activity size={32} color="#3b82f6" />
          <h1>eBay Arbitrage Engine</h1>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            {filteredData.length} Deals Found
          </span>
        </div>
      </header>

      <div className="glass-panel" style={{ padding: '2rem' }}>
        
        <div className="tabs-container">
          <button 
            className={`tab-button ${activeTab === 'live' ? 'active' : ''}`}
            onClick={() => setActiveTab('live')}
          >
            <Clock size={18} />
            Live Sniper
          </button>
          <button 
            className={`tab-button ${activeTab === 'sweep' ? 'active' : ''}`}
            onClick={() => setActiveTab('sweep')}
          >
            <CheckCircle2 size={18} />
            Deep Sweep
          </button>
        </div>

        <div className="controls-bar" style={{ marginBottom: '1rem' }}>
          <div className="search-container">
            <div className="search-input-wrapper">
              <Search className="search-icon" />
              <input 
                type="text" 
                className="search-input" 
                placeholder="Search watches, brands, keywords..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <select 
              className="search-select" 
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setCurrentPage(1);
              }}
            >
              {['All', ...new Set(data.map(item => item.Query).filter(Boolean))].map((cat, i) => (
                <option key={i} value={cat}>{cat === 'All' ? 'All Brands & Models' : cat}</option>
              ))}
            </select>
          </div>
          
          <div className="action-buttons-container">
            {activeTab === 'live' && (
              <>
                <button 
                  className={`btn ${soundEnabled ? 'btn-sound-on' : 'btn-outline'}`}
                  onClick={toggleSound}
                  style={{ padding: '0.5rem 1rem' }}
                >
                  {soundEnabled ? '🔊 Sound ON' : '🔈 Sound OFF'}
                </button>
                <label className="auto-refresh-label">
                  <input 
                    type="checkbox" 
                    checked={isAutoPolling} 
                    onChange={(e) => setIsAutoPolling(e.target.checked)}
                  />
                  Auto-Refresh
                </label>
              </>
            )}
            <button className="btn btn-outline" onClick={() => fetchData(activeTab)}>
              Refresh
            </button>
            <button className="btn" onClick={downloadCSV}>
              <Download size={18} />
              Export CSV
            </button>
          </div>
        </div>

        {/* Quick Filter Chips */}
        <div className="filter-chips-container">
          <button className={`badge ${filters.mens ? 'badge-blue' : 'badge-inactive'}`} onClick={() => toggleFilter('mens')}>🔵 Mens</button>
          <button className={`badge ${filters.womens ? 'badge-gold' : 'badge-inactive'}`} onClick={() => toggleFilter('womens')}>🔴 Womens</button>
          <button className={`badge ${filters.bidding ? 'badge-blue' : 'badge-inactive'}`} onClick={() => toggleFilter('bidding')}>💰 Bidding</button>
          <button className={`badge ${filters.buyItNow ? 'badge-blue' : 'badge-inactive'}`} onClick={() => toggleFilter('buyItNow')}>⚡ Buy It Now</button>
          <button className={`badge ${filters.acceptsOffers ? 'badge-blue' : 'badge-inactive'}`} onClick={() => toggleFilter('acceptsOffers')}>🤝 Accepts Offers</button>
          <button className={`badge ${filters.belowScrap ? 'badge-gold' : 'badge-inactive'}`} onClick={() => toggleFilter('belowScrap')}>🔥 Below Scrap Value</button>
        </div>

        {loading ? (
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Scanning global markets...</p>
          </div>
        ) : (
          <div className="fade-in">
            {currentData.length > 0 ? (
              <div className="card-grid">
                {currentData.map((item, index) => {
                  const isBelowScrap = item.ScrapValue && item.ScrapValue !== 'N/A' && item.Price < parseInt(item.ScrapValue.replace('$', ''));
                  return (
                    <div className={`deal-card ${isBelowScrap ? 'deal-card-highlight' : ''}`} key={index}>
                      <div className="deal-card-image">
                        {item.ImageUrl ? (
                          <img src={item.ImageUrl} alt={item.Title} />
                        ) : (
                          <div className="no-img-placeholder">No Image</div>
                        )}
                      </div>
                      
                      <div className="deal-card-content">
                        <div className="deal-card-header">
                          <h3 className="deal-title">{item.Title}</h3>
                          <div className="deal-badges">
                            {item.Condition && <span className="badge badge-blue">{item.Condition}</span>}
                            {item.Health && item.Health !== 'CLEAN' && <span className="badge badge-danger">{item.Health.replace(/\[|\]/g, '')}</span>}
                          </div>
                        </div>
                        
                        <div className="deal-details-grid">
                          <div className="detail-item">
                            <span className="detail-label">Price</span>
                            <span className="detail-value price-value">${item.Price}</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Scrap Value</span>
                            {item.ScrapValue !== 'N/A' ? (
                              <span className="badge badge-gold">{item.ScrapValue}</span>
                            ) : (
                              <span className="detail-value text-muted">-</span>
                            )}
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Time Left</span>
                            <span className="detail-value time-value">{item.TimeLeft}</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Listed</span>
                            <span className="detail-value">{item.TimeListed || 'Unknown'}</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Gender</span>
                            <span className="detail-value">{item.Gender}</span>
                          </div>
                          <div className="detail-item">
                            <span className="detail-label">Format</span>
                            <span className="detail-value">{item.BuyingOptions}</span>
                          </div>
                        </div>
                        
                        <div className="deal-card-actions">
                          <button 
                            className="btn btn-outline" 
                            title="Hide this item"
                            onClick={() => hideItem(item.Link)}
                            style={{ flex: 1, color: 'var(--danger)', borderColor: 'var(--border-color)' }}
                          >
                            <Trash2 size={16} /> Hide
                          </button>
                          <button 
                            className="btn btn-outline" 
                            title="Copy Link"
                            onClick={() => copyToClipboard(item.Link)}
                            style={{ flex: 1 }}
                          >
                            <Copy size={16} /> Copy
                          </button>
                          <a 
                            href={item.Link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="btn"
                            title="Open in eBay"
                            style={{ flex: 2, justifyContent: 'center' }}
                          >
                            <ExternalLink size={16} /> Open eBay
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <p>No deals found. Try adjusting your filters or search.</p>
              </div>
            )}
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="pagination-container">
                <span className="pagination-info">
                  Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, filteredData.length)} of {filteredData.length} entries
                </span>
                <div className="pagination-buttons">
                  <button 
                    className="btn btn-outline" 
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span className="pagination-page-indicator">Page {currentPage} of {totalPages}</span>
                  <button 
                    className="btn btn-outline" 
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
