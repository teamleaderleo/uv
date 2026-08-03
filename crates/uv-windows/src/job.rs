//! Windows Job Objects for process lifecycle management.
//!
//! Job Objects allow grouping processes together and applying limits. The key feature
//! used here is `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, which ensures that when the job
//! handle is closed (e.g., when the parent process exits), all processes in the job are
//! terminated.
//!
//! This is essential for wrapper processes (like `uvx.exe` or the Python trampoline)
//! to ensure child processes don't become orphaned when the wrapper is killed.

use core::ffi::c_void;
#[cfg(feature = "std")]
use std::os::windows::io::{AsRawHandle, FromRawHandle, OwnedHandle};

#[cfg(not(feature = "std"))]
use windows::Win32::Foundation::CloseHandle;
use windows::Win32::Foundation::HANDLE;
use windows::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JobObjectExtendedLimitInformation, QueryInformationJobObject, SetInformationJobObject,
};

/// Error type for job object operations.
#[derive(Debug, Clone, Copy)]
pub enum JobError {
    /// Failed to create job object.
    Create(i32),
    /// Failed to query job object information.
    Query(i32),
    /// Failed to set job object information.
    Set(i32),
    /// Failed to assign process to job object.
    Assign(i32),
}

impl JobError {
    /// Returns Windows error code associated with this error.
    #[must_use]
    pub const fn code(&self) -> i32 {
        match *self {
            Self::Create(code) | Self::Query(code) | Self::Set(code) | Self::Assign(code) => code,
        }
    }

    /// Returns static description of error kind.
    #[must_use]
    pub const fn message(&self) -> &'static str {
        match self {
            Self::Create(_) => "failed to create job object",
            Self::Query(_) => "failed to query job object information",
            Self::Set(_) => "failed to set job object information",
            Self::Assign(_) => "failed to assign process to job object",
        }
    }
}

#[cfg(feature = "std")]
impl std::fmt::Display for JobError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} (os error {})", self.message(), self.code())
    }
}

#[cfg(feature = "std")]
impl std::error::Error for JobError {}

/// A Windows Job Object configured to terminate assigned processes when closed.
///
/// [`Job::new`] preserves existing wrapper-oriented behavior: child processes may silently
/// break away so they can create or join their own jobs. [`Job::new_strict_tree`] is experimental
/// alternative for process trees that must remain supervised through descendants.
pub struct Job {
    /// `OwnedHandle` supplies single-owner close semantics and standard-library thread mobility.
    #[cfg(feature = "std")]
    handle: OwnedHandle,
    /// The no-std build retains the existing raw-handle owner and explicit `Drop` implementation.
    #[cfg(not(feature = "std"))]
    handle: HANDLE,
}

impl Job {
    /// Creates existing wrapper-oriented job object.
    ///
    /// Job is configured with:
    /// - `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: terminate assigned processes when handle closes;
    /// - `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`: descendants are not automatically retained in job,
    ///   preserving compatibility with children that manage their own job objects.
    pub fn new() -> Result<Self, JobError> {
        Self::new_with_silent_breakaway(true)
    }

    /// Creates experimental strict process-tree job object.
    ///
    /// Descendants inherit membership by default because no breakaway limit is enabled. This is a
    /// stronger cleanup contract, but descendant that requires its own incompatible job object may
    /// fail. Fieldwork self-update experiment compares both policies before any product use.
    pub fn new_strict_tree() -> Result<Self, JobError> {
        Self::new_with_silent_breakaway(false)
    }

    #[allow(unsafe_code)]
    fn new_with_silent_breakaway(silent_breakaway: bool) -> Result<Self, JobError> {
        // SAFETY: CreateJobObjectW with None parameters creates unnamed job object.
        let handle =
            unsafe { CreateJobObjectW(None, None) }.map_err(|e| JobError::Create(e.code().0))?;

        #[cfg(feature = "std")]
        let job = Self {
            // SAFETY: `CreateJobObjectW` returned a newly owned valid handle. Ownership transfers
            // exactly once to `OwnedHandle`, which closes it on drop.
            handle: unsafe { OwnedHandle::from_raw_handle(handle.0) },
        };
        #[cfg(not(feature = "std"))]
        let job = Self { handle };

        job.configure_limits(silent_breakaway)?;
        Ok(job)
    }

    #[must_use]
    fn raw_handle(&self) -> HANDLE {
        #[cfg(feature = "std")]
        {
            HANDLE(self.handle.as_raw_handle())
        }
        #[cfg(not(feature = "std"))]
        {
            self.handle
        }
    }

    /// Assigns standard-library child process to this job object.
    #[cfg(feature = "std")]
    #[allow(unsafe_code)]
    pub fn assign_child(&self, child: &std::process::Child) -> Result<(), JobError> {
        use std::os::windows::io::{AsHandle, AsRawHandle};

        let handle = child.as_handle();
        // SAFETY: `handle` borrows live `Child` process handle for this call.
        unsafe { self.assign_process(HANDLE(handle.as_raw_handle())) }
    }

    /// Assigns raw Windows process handle to this job object.
    ///
    /// # Safety
    ///
    /// Caller must ensure raw handle refers to live process for duration of call.
    #[cfg(feature = "std")]
    #[allow(unsafe_code)]
    pub unsafe fn assign_raw_process_handle(
        &self,
        raw_handle: *mut c_void,
    ) -> Result<(), JobError> {
        // SAFETY: Caller establishes raw handle validity for this assignment call.
        unsafe { self.assign_process(HANDLE(raw_handle)) }
    }

    /// Assigns process to this job object.
    ///
    /// # Safety
    ///
    /// Caller must ensure `process_handle` is valid process handle.
    #[allow(unsafe_code)]
    pub unsafe fn assign_process(&self, process_handle: HANDLE) -> Result<(), JobError> {
        // SAFETY: Caller guarantees process_handle is valid. The job handle remains valid because
        // it is owned by `self` until drop.
        unsafe { AssignProcessToJobObject(self.raw_handle(), process_handle) }
            .map_err(|e| JobError::Assign(e.code().0))
    }

    #[allow(unsafe_code)]
    fn configure_limits(&self, silent_breakaway: bool) -> Result<(), JobError> {
        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        let info_size = u32::try_from(size_of_val(&info)).expect("job info size fits in u32");
        let handle = self.raw_handle();

        // SAFETY: We pass valid job handle, correct information class, properly sized buffer,
        // and buffer size.
        unsafe {
            QueryInformationJobObject(
                Some(handle),
                JobObjectExtendedLimitInformation,
                (&raw mut info).cast::<c_void>(),
                info_size,
                None,
            )
        }
        .map_err(|e| JobError::Query(e.code().0))?;

        info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if silent_breakaway {
            info.BasicLimitInformation.LimitFlags |= JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK;
        }

        // SAFETY: We pass valid job handle, correct information class, properly initialized info
        // struct, and its size.
        unsafe {
            SetInformationJobObject(
                handle,
                JobObjectExtendedLimitInformation,
                (&raw const info).cast::<c_void>(),
                info_size,
            )
        }
        .map_err(|e| JobError::Set(e.code().0))
    }
}

#[cfg(not(feature = "std"))]
impl Drop for Job {
    #[allow(unsafe_code)]
    fn drop(&mut self) {
        // SAFETY: self.handle is valid and owned by this object.
        let _ = unsafe { CloseHandle(self.handle) };
    }
}
