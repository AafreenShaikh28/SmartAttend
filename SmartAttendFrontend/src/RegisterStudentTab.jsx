import { useState, useEffect, useRef } from 'react';

function RegisterStudentTab() {
  const [name, setName] = useState('');
  const [rollNo, setRollNo] = useState('');
  const [branch, setBranch] = useState('');
  const [semester, setSemester] = useState('');
  const [images, setImages] = useState([]);
  const [imagePreviews, setImagePreviews] = useState([]);
  
  // Validation errors
  const [errors, setErrors] = useState({});
  
  // API loading / response states
  const [isLoading, setIsLoading] = useState(false);
  const [successData, setSuccessData] = useState(null);
  const [error, setError] = useState(null);

  // Keep track of all created object URLs to revoke them on unmount
  const activeUrlsRef = useRef([]);

  useEffect(() => {
    return () => {
      activeUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    };
  }, []);

  const validateImagesCount = (currentImages) => {
    if (currentImages.length < 5 || currentImages.length > 10) {
      setErrors(prev => ({
        ...prev,
        images: `Please select between 5 and 10 images (currently selected: ${currentImages.length})`
      }));
    } else {
      setErrors(prev => {
        const copy = { ...prev };
        delete copy.images;
        return copy;
      });
    }
  };

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    // Append new files to the existing array rather than replacing it
    const updatedImages = [...images, ...selectedFiles];
    setImages(updatedImages);

    // Generate and append new previews
    const newPreviews = selectedFiles.map(file => {
      const url = URL.createObjectURL(file);
      activeUrlsRef.current.push(url);
      return url;
    });
    setImagePreviews(prev => [...prev, ...newPreviews]);

    // Reset input element value to allow re-selecting same files if removed
    if (e.target) {
      e.target.value = '';
    }

    validateImagesCount(updatedImages);
  };

  const removeImage = (indexToRemove) => {
    const urlToRemove = imagePreviews[indexToRemove];
    if (urlToRemove) {
      URL.revokeObjectURL(urlToRemove);
      activeUrlsRef.current = activeUrlsRef.current.filter(url => url !== urlToRemove);
    }

    const updatedImages = images.filter((_, idx) => idx !== indexToRemove);
    const updatedPreviews = imagePreviews.filter((_, idx) => idx !== indexToRemove);

    setImages(updatedImages);
    setImagePreviews(updatedPreviews);

    validateImagesCount(updatedImages);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessData(null);

    // Perform validation
    const validationErrors = {};
    if (!name.trim()) validationErrors.name = 'Student Name is required';
    if (!rollNo.trim()) validationErrors.rollNo = 'Roll Number is required';
    if (!branch.trim()) validationErrors.branch = 'Branch is required';
    
    // Semester validation
    const semInt = parseInt(semester, 10);
    if (!semester) {
      validationErrors.semester = 'Semester is required';
    } else if (isNaN(semInt) || semInt <= 0 || semInt.toString() !== semester.trim()) {
      validationErrors.semester = 'Semester must be a positive integer';
    }

    // Images count validation
    if (images.length < 5 || images.length > 10) {
      validationErrors.images = `Please select between 5 and 10 images (currently selected: ${images.length})`;
    } else {
      // Validate extensions
      const allowedExtensions = ['jpg', 'jpeg', 'png'];
      const invalidFiles = images.filter(file => {
        const ext = file.name.split('.').pop().toLowerCase();
        return !allowedExtensions.includes(ext);
      });
      if (invalidFiles.length > 0) {
        validationErrors.images = 'Only .jpg, .jpeg, and .png images are allowed';
      }
    }

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('name', name.trim());
      formData.append('roll_no', rollNo.trim());
      formData.append('branch', branch.trim());
      formData.append('semester', semInt);
      
      images.forEach(file => {
        formData.append('images', file);
      });

      const response = await fetch('http://127.0.0.1:8000/students/register', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        let errorMsg = 'An error occurred during registration.';
        if (data && data.detail) {
          if (typeof data.detail === 'string') {
            errorMsg = data.detail;
          } else if (Array.isArray(data.detail)) {
            errorMsg = data.detail.map(err => `${err.loc ? err.loc.join('.') : 'Field'}: ${err.msg}`).join(', ');
          } else {
            errorMsg = JSON.stringify(data.detail);
          }
        }
        throw new Error(errorMsg);
      }

      setSuccessData(data);
      
      // Reset form on success
      setName('');
      setRollNo('');
      setBranch('');
      setSemester('');
      setImages([]);
      activeUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
      activeUrlsRef.current = [];
      setImagePreviews([]);
      
      // Reset input element
      const fileInput = document.getElementById('student-images-input');
      if (fileInput) fileInput.value = '';

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card-container">
      <div className="card-header">
        <h2>Register Student</h2>
        <p>Register a new student with 5 to 10 sample face images for training the recognition model.</p>
      </div>

      <form onSubmit={handleSubmit} className="form-layout">
        <div className="form-group">
          <label htmlFor="student-name">Student Name *</label>
          <input
            id="student-name"
            type="text"
            placeholder="e.g. John Doe"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isLoading}
            className={errors.name ? 'input-error' : ''}
          />
          {errors.name && <span className="error-text">{errors.name}</span>}
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="student-roll-no">Roll Number *</label>
            <input
              id="student-roll-no"
              type="text"
              placeholder="e.g. 20BCS001"
              value={rollNo}
              onChange={(e) => setRollNo(e.target.value)}
              disabled={isLoading}
              className={errors.rollNo ? 'input-error' : ''}
            />
            {errors.rollNo && <span className="error-text">{errors.rollNo}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="student-branch">Branch *</label>
            <input
              id="student-branch"
              type="text"
              placeholder="e.g. CSE, ECE"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={isLoading}
              className={errors.branch ? 'input-error' : ''}
            />
            {errors.branch && <span className="error-text">{errors.branch}</span>}
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="student-semester">Semester (Positive Integer) *</label>
          <input
            id="student-semester"
            type="number"
            placeholder="e.g. 6"
            value={semester}
            onChange={(e) => setSemester(e.target.value)}
            disabled={isLoading}
            className={errors.semester ? 'input-error' : ''}
            min="1"
            step="1"
          />
          {errors.semester && <span className="error-text">{errors.semester}</span>}
        </div>

        <div className="form-group">
          <label htmlFor="student-images-input">
            Face Images (5 to 10 files, JPG/JPEG/PNG) *
          </label>
          <div className="file-dropzone">
            <input
              id="student-images-input"
              type="file"
              multiple
              accept=".jpg,.jpeg,.png,image/jpeg,image/png"
              onChange={handleFileChange}
              disabled={isLoading}
              className="hidden-file-input"
            />
            <div className="dropzone-ui">
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="dropzone-icon">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <span>Click to upload or drag & drop files</span>
              <span className="dropzone-sub">Accepts .jpg, .jpeg, .png</span>
            </div>
          </div>
          {errors.images && <span className="error-text">{errors.images}</span>}
          
          {imagePreviews.length > 0 && (
            <div className="previews-container">
              <div className="previews-header">
                Selected files ({imagePreviews.length})
              </div>
              <div className="previews-grid">
                {imagePreviews.map((url, idx) => (
                  <div key={idx} className="preview-item">
                    <button
                      type="button"
                      onClick={() => removeImage(idx)}
                      className="remove-preview-btn"
                      title="Remove image"
                      disabled={isLoading}
                    >
                      &times;
                    </button>
                    <img src={url} alt={`Preview ${idx + 1}`} />
                    <div className="preview-label">{images[idx]?.name || `Image ${idx + 1}`}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button type="submit" disabled={isLoading} className="btn-primary">
          {isLoading ? (
            <div className="btn-spinner-container">
              <span className="spinner"></span>
              <span>Registering Student...</span>
            </div>
          ) : (
            'Register Student'
          )}
        </button>
      </form>

      {/* Success Panel */}
      {successData && (
        <div className="panel-success fade-in">
          <div className="panel-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="success-icon">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <h3>Registration Successful</h3>
          </div>
          <div className="panel-body">
            <p><strong>Message:</strong> {successData.message || 'Student registered successfully!'}</p>
            <p><strong>Student ID:</strong> <code>{successData.student_id}</code></p>
            {successData.images_saved && successData.images_saved.length > 0 && (
              <div className="saved-images-list">
                <strong>Saved Images:</strong>
                <ul>
                  {successData.images_saved.map((imgName, i) => (
                    <li key={i}><code>{imgName}</code></li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Error Panel */}
      {error && (
        <div className="panel-error fade-in">
          <div className="panel-header">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="error-icon">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <h3>Registration Failed</h3>
          </div>
          <div className="panel-body">
            <p className="error-message-text">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default RegisterStudentTab;
