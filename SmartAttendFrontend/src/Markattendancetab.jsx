import { useState, useEffect, useRef } from 'react';

function MarkAttendanceTab() {
    const [image, setImage] = useState(null);
    const [imagePreview, setImagePreview] = useState(null);

    // Validation errors
    const [errors, setErrors] = useState({});

    // API loading / response states
    const [isLoading, setIsLoading] = useState(false);
    const [successData, setSuccessData] = useState(null);
    const [error, setError] = useState(null);

    // Track the created object URL to revoke it on unmount / replace
    const activeUrlRef = useRef(null);

    useEffect(() => {
        return () => {
            if (activeUrlRef.current) {
                URL.revokeObjectURL(activeUrlRef.current);
            }
        };
    }, []);

    const handleFileChange = (e) => {
        const selectedFile = (e.target.files || [])[0];
        if (!selectedFile) return;

        if (activeUrlRef.current) {
            URL.revokeObjectURL(activeUrlRef.current);
        }

        const url = URL.createObjectURL(selectedFile);
        activeUrlRef.current = url;

        setImage(selectedFile);
        setImagePreview(url);
        setErrors({});

        // Reset input element value to allow re-selecting the same file
        if (e.target) {
            e.target.value = '';
        }
    };

    const removeImage = () => {
        if (activeUrlRef.current) {
            URL.revokeObjectURL(activeUrlRef.current);
            activeUrlRef.current = null;
        }
        setImage(null);
        setImagePreview(null);

        const fileInput = document.getElementById('classroom-image-input');
        if (fileInput) fileInput.value = '';
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccessData(null);

        // Perform validation
        const validationErrors = {};
        if (!image) {
            validationErrors.image = 'A classroom image is required';
        } else {
            const allowedExtensions = ['jpg', 'jpeg', 'png'];
            const ext = image.name.split('.').pop().toLowerCase();
            if (!allowedExtensions.includes(ext)) {
                validationErrors.image = 'Only .jpg, .jpeg, and .png images are allowed';
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
            formData.append('image', image);

            const response = await fetch('http://127.0.0.1:8000/attendance', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                let errorMsg = 'An error occurred while processing attendance.';
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
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    };

    const results = successData?.results || [];
    const recognizedCount = results.filter((r) => r && r !== 'unknown').length;
    const unknownCount = results.length - recognizedCount;

    return (
        <div className="card-container">
            <div className="card-header">
                <h2>Mark Attendance</h2>
                <p>Upload a classroom photo to detect faces and match them against registered students.</p>
            </div>

            <form onSubmit={handleSubmit} className="form-layout">
                <div className="form-group">
                    <label htmlFor="classroom-image-input">
                        Classroom Photo (JPG/JPEG/PNG) *
                    </label>
                    <div className="file-dropzone">
                        <input
                            id="classroom-image-input"
                            type="file"
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
                            <span>Click to upload or drag & drop a classroom photo</span>
                            <span className="dropzone-sub">Accepts .jpg, .jpeg, .png</span>
                        </div>
                    </div>
                    {errors.image && <span className="error-text">{errors.image}</span>}

                    {imagePreview && (
                        <div className="previews-container">
                            <div className="previews-header">Selected file</div>
                            <div className="previews-grid">
                                <div className="preview-item">
                                    <button
                                        type="button"
                                        onClick={removeImage}
                                        className="remove-preview-btn"
                                        title="Remove image"
                                        disabled={isLoading}
                                    >
                                        &times;
                                    </button>
                                    <img src={imagePreview} alt="Classroom preview" />
                                    <div className="preview-label">{image?.name}</div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <button type="submit" disabled={isLoading} className="btn-primary">
                    {isLoading ? (
                        <div className="btn-spinner-container">
                            <span className="spinner"></span>
                            <span>Processing Attendance...</span>
                        </div>
                    ) : (
                        'Mark Attendance'
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
                        <h3>Attendance Processed</h3>
                    </div>
                    <div className="panel-body">
                        <p><strong>Message:</strong> {successData.message || 'Attendance processed successfully!'}</p>

                        {results.length === 0 ? (
                            <p>No faces were detected in the uploaded image.</p>
                        ) : (
                            <>
                                <p>
                                    <strong>Faces detected:</strong> {results.length}
                                    {' '}(<strong>{recognizedCount}</strong> recognized, <strong>{unknownCount}</strong> unknown)
                                </p>
                                <div className="saved-images-list">
                                    <strong>Roll Numbers:</strong>
                                    <ul>
                                        {results.map((rollNo, i) => (
                                            <li key={i}>
                                                <code>{rollNo === 'unknown' ? 'Unknown face' : rollNo}</code>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </>
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
                        <h3>Attendance Failed</h3>
                    </div>
                    <div className="panel-body">
                        <p className="error-message-text">{error}</p>
                    </div>
                </div>
            )}
        </div>
    );
}

export default MarkAttendanceTab;