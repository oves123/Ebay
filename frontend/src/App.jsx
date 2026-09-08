import React, { useState, useEffect } from 'react';
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
  const [lastLatestLink, setLastLatestLink] = useState(null);

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
        if (!lastLatestLink) {
          setLastLatestLink(currentLatestLink);
        } else if (currentLatestLink !== lastLatestLink) {
          // A new snipe has arrived!
          setLastLatestLink(currentLatestLink);
          playDing();
        }
      } else if (!isSilent && tab === 'live' && newData.length > 0) {
          setLastLatestLink(newData[0].Link);
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
      audio.play().catch(e => console.log('Audio play failed', e));
    } catch (err) { }
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
            {data.length} Deals Found
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
          <div className="search-container" style={{ display: 'flex', gap: '1rem', flex: 1 }}>
            <div style={{ position: 'relative', flex: 1, maxWidth: '400px' }}>
              <Search className="search-icon" />
              <input 
                type="text" 
                className="search-input" 
                style={{ width: '100%' }}
                placeholder="Search watches, brands, keywords..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            
            <select 
              className="search-input" 
              style={{ paddingLeft: '1rem', width: 'auto', minWidth: '200px' }}
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
          
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            {activeTab === 'live' && (
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                <input 
                  type="checkbox" 
                  checked={isAutoPolling} 
                  onChange={(e) => setIsAutoPolling(e.target.checked)}
                />
                Auto-Refresh
              </label>
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
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          <button className={`badge ${filters.mens ? 'badge-blue' : ''}`} style={{ cursor: 'pointer', border: filters.mens ? '' : '1px solid var(--border-color)', background: filters.mens ? '' : 'transparent', color: filters.mens ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('mens')}>🔵 Mens</button>
          <button className={`badge ${filters.womens ? 'badge-gold' : ''}`} style={{ cursor: 'pointer', border: filters.womens ? '' : '1px solid var(--border-color)', background: filters.womens ? '' : 'transparent', color: filters.womens ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('womens')}>🔴 Womens</button>
          <button className={`badge ${filters.bidding ? 'badge-blue' : ''}`} style={{ cursor: 'pointer', border: filters.bidding ? '' : '1px solid var(--border-color)', background: filters.bidding ? '' : 'transparent', color: filters.bidding ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('bidding')}>💰 Bidding</button>
          <button className={`badge ${filters.buyItNow ? 'badge-blue' : ''}`} style={{ cursor: 'pointer', border: filters.buyItNow ? '' : '1px solid var(--border-color)', background: filters.buyItNow ? '' : 'transparent', color: filters.buyItNow ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('buyItNow')}>⚡ Buy It Now</button>
          <button className={`badge ${filters.acceptsOffers ? 'badge-blue' : ''}`} style={{ cursor: 'pointer', border: filters.acceptsOffers ? '' : '1px solid var(--border-color)', background: filters.acceptsOffers ? '' : 'transparent', color: filters.acceptsOffers ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('acceptsOffers')}>🤝 Accepts Offers</button>
          <button className={`badge ${filters.belowScrap ? 'badge-gold' : ''}`} style={{ cursor: 'pointer', border: filters.belowScrap ? '' : '1px solid var(--border-color)', background: filters.belowScrap ? '' : 'transparent', color: filters.belowScrap ? '' : 'var(--text-secondary)' }} onClick={() => toggleFilter('belowScrap')}>🔥 Below Scrap Value</button>
        </div>

        {loading ? (
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Scanning global markets...</p>
          </div>
        ) : (
          <div className="table-container fade-in">
            <table>
              <thead>
                <tr>
                  <th>Image</th>
                  <th>Title</th>
                  <th>Format & Gender</th>
                  <th>Price</th>
                  <th>Listed / Time Left</th>
                  <th>Scrap Value</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {currentData.length > 0 ? (
                  currentData.map((item, index) => {
                    const isBelowScrap = item.ScrapValue && item.ScrapValue !== 'N/A' && item.Price < parseInt(item.ScrapValue.replace('$', ''));
                    return (
                    <tr key={index} style={{ backgroundColor: isBelowScrap ? 'rgba(16, 185, 129, 0.05)' : '' }}>
                      <td className="cell-image">
                        {item.ImageUrl ? (
                          <img src={item.ImageUrl} alt="Watch" />
                        ) : (
                          <div style={{ width: '60px', height: '60px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>No Img</div>
                        )}
                      </td>
                      <td className="cell-title">
                        <div style={{ marginBottom: '4px' }}>{item.Title}</div>
                        {item.Condition && <span className="badge badge-blue" style={{ marginRight: '8px' }}>{item.Condition}</span>}
                        {item.Health && item.Health !== 'CLEAN' && <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444' }}>{item.Health}</span>}
                      </td>
                      <td>
                        <div style={{ fontSize: '1.05rem', marginBottom: '6px', fontWeight: '500' }}>{item.Gender}</div>
                        <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)' }}>{item.BuyingOptions}</div>
                      </td>
                      <td className="cell-price">${item.Price}</td>
                      <td>
                        <div style={{ fontSize: '1.05rem', marginBottom: '6px', fontWeight: '500' }}>{item.TimeLeft} left</div>
                        <div style={{ fontSize: '0.95rem', color: 'var(--text-secondary)' }}>Listed: {item.TimeListed || 'Unknown'}</div>
                      </td>
                      <td>
                        {item.ScrapValue !== 'N/A' ? (
                          <span className="badge badge-gold">{item.ScrapValue}</span>
                        ) : (
                          <span style={{ color: 'var(--text-secondary)' }}>-</span>
                        )}
                      </td>
                      <td>
                        <div className="cell-actions">
                          <button 
                            className="action-btn" 
                            title="Hide this item"
                            onClick={() => hideItem(item.Link)}
                            style={{ color: 'var(--danger)' }}
                          >
                            <Trash2 size={16} />
                          </button>
                          <button 
                            className="action-btn" 
                            title="Copy Link"
                            onClick={() => copyToClipboard(item.Link)}
                          >
                            <Copy size={16} />
                          </button>
                          <a 
                            href={item.Link} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="action-btn"
                            title="Open in eBay"
                          >
                            <ExternalLink size={16} />
                          </a>
                        </div>
                      </td>
                    </tr>
                  )})
                ) : (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                      No deals found. Try a different search.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid var(--border-color)', backgroundColor: '#f8fafc' }}>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                  Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, filteredData.length)} of {filteredData.length} entries
                </span>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button 
                    className="btn btn-outline" 
                    style={{ padding: '0.5rem 1rem' }}
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  >
                    Previous
                  </button>
                  <span style={{ padding: '0.5rem', fontWeight: '500' }}>Page {currentPage} of {totalPages}</span>
                  <button 
                    className="btn btn-outline" 
                    style={{ padding: '0.5rem 1rem' }}
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
