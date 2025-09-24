import os
import datetime

def create_save_filename(database_folder, filename):
    """
    Creates a file name with the current date and a number. The number is incremented if the file already exists.
    A database folder is created if it doesn't exist. It is organized by year, month and day.

    Parameters
    ----------
    database_folder : string
        Root path to the folder where the file will be saved and the database created if it doesn't exist.
    filename : string
        Name of the file without the date and number. Used to describe the data.

    Returns
    -------
    day_folder : string
        Path to the folder where the file will be saved.
    file_name : string
        Name of the file with the date and number.
    """
    # Get the current date
    now = datetime.datetime.now()
    year = str(now.year)
    month = "{:02}".format(now.month)
    day = "{:02}".format(now.day)

    # Create the folder for the month if it doesn't exist
    month_folder = os.path.join(database_folder, year, month)
    if not os.path.exists(month_folder):
        os.makedirs(month_folder)

    # Create the folder for the day if it doesn't exist
    day_folder = os.path.join(month_folder, day)
    if not os.path.exists(day_folder):
        os.makedirs(day_folder)

    # Generate the file name
    num_increment = 1
    file_name = "{}_{}_{:04}.txt".format(datetime.datetime.now().strftime("%Y%m%d"), filename, num_increment)

    # Check if the file already exists in the day folder
    while os.path.exists(os.path.join(day_folder, file_name)):
        num_increment = int(file_name[-8:-4]) + 1
        file_name = "{}_{}_{:04}.txt".format(datetime.datetime.now().strftime("%Y%m%d"), filename, num_increment)

    return day_folder, file_name

if __name__ == "__main__":
    # Example usage
    filename = create_save_filename(os.path.join(os.path.dirname(os.path.realpath(__file__))), "test")
    print(filename)
    # Save the file in the day folder
    with open(filename, 'w') as file:
        # Write the contents of the file
        file.write("Hello, World!")
        

