from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
import io
from sales_mix_processor import process_data

app = FastAPI(title="Sales Mix API", version="1.0.0")

# Enable CORS for the zifapp frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Sales Mix API", "version": "1.0.0"}


@app.post("/process")
async def process_sales_mix(file: UploadFile = File(...)):
    """
    Process sales mix CSV file.

    Args:
        file: CSV file upload (expects header at row 4)

    Returns:
        JSON response with processed data
    """
    try:
        # Read the uploaded file
        contents = await file.read()

        # Parse CSV with header at row 3 (0-indexed)
        raw_df = pd.read_csv(io.BytesIO(contents), header=3)

        # Process the data
        final_ordered_data, final_display_data = process_data(raw_df)

        # Convert to JSON-friendly format
        return JSONResponse(content={
            "status": "success",
            "data": {
                "ordered": final_ordered_data.to_dict(orient="records"),
                "display": final_display_data.to_dict(orient="records")
            }
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@app.post("/process/csv")
async def process_sales_mix_csv(file: UploadFile = File(...)):
    """
    Process sales mix CSV file and return CSV output.

    Args:
        file: CSV file upload (expects header at row 4)

    Returns:
        CSV file download
    """
    try:
        # Read the uploaded file
        contents = await file.read()

        # Parse CSV with header at row 3 (0-indexed)
        raw_df = pd.read_csv(io.BytesIO(contents), header=3)

        # Process the data
        final_ordered_data, _ = process_data(raw_df)

        # Convert to CSV
        output = io.StringIO()
        final_ordered_data.to_csv(output, index=False)
        output.seek(0)

        # Return as downloadable file
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=processed_sales_mix_data.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
